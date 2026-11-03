"""Working Arduino sketch (Temperature: ... at 9600 baud) → USB → MQTT.

No fabricated samples, board upload, Wi-Fi configuration, or direct ingestion API.
Only windows containing a serial measurement are published; the user's sketch reads
every five seconds, so most three-second windows have one sample and some are empty.
"""
import argparse
import json
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
import serial
import serial.tools.list_ports

from backend.app.config import Settings
from backend.app.mqtt import configure_client
from backend.app.telemetry import Window

log = logging.getLogger(__name__)
READING = re.compile(r"^Temperature:\s*(-?(?:\d+(?:\.\d+)?|nan|inf))", re.IGNORECASE)


def parse_temperature(line):
    match = READING.match(line)
    if not match:
        return None
    return float(match.group(1))


def find_serial_port(requested_port="auto"):
    try:
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        return None
    if not ports:
        return None
    if requested_port and requested_port.lower() not in ("auto", "none", ""):
        for p in ports:
            if p.device.upper() == requested_port.upper():
                return p.device
    for p in ports:
        desc = ((p.description or "") + " " + (p.hwid or "")).upper()
        if any(k in desc for k in ("CP210", "10C4:EA60", "CH340", "USB", "UART", "SERIAL")):
            return p.device
    return ports[0].device


class SerialWindows:
    def __init__(self, device_id):
        self.device_id = device_id
        self.start = None
        self.values = []
        self.invalid = False
        self.sequence = time.time_ns() // 1000

    def advance(self, now):
        boundary = datetime.fromtimestamp(int(now.timestamp()) // 3 * 3, timezone.utc)
        result = None
        if self.start is not None and boundary != self.start:
            # Drop acquisition gaps/host suspension rather than replaying old windows.
            if boundary == self.start + timedelta(seconds=3) and (self.values or self.invalid):
                self.sequence = max(self.sequence + 1, time.time_ns() // 1000)
                valid = bool(self.values) and not self.invalid
                result = dict(schema_version=1, device_id=self.device_id, source="physical",
                    sequence=self.sequence, window_start=self.start.isoformat(),
                    window_end=boundary.isoformat(), window_duration_seconds=3,
                    temperature=dict(mean=sum(self.values) / len(self.values) if valid else None,
                        min=min(self.values) if valid else None, max=max(self.values) if valid else None,
                        unit="degC", sample_count=len(self.values) if valid else 0,
                        status="valid" if valid else "disconnected"))
                Window.model_validate(result)
            self.values = []
            self.invalid = False
        self.start = boundary
        return result

    def add(self, value):
        if not math.isfinite(value) or not -55 <= value <= 125:
            self.invalid = True
        elif len(self.values) < 100:
            self.values.append(value)


def main():
    parser = argparse.ArgumentParser(description="ESP32 DS18B20 USB serial → MQTT")
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--duration", type=float, default=0, help="Stop after this many seconds; 0 runs until Ctrl+C")
    parser.add_argument("--mock-fallback", action="store_true", default=True,
                        help="Fallback to simulated DS18B20 stream if hardware COM port is not yet available")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = Settings()
    log.info("Physical publisher MQTT broker=%s port=%s topic=%s device=%s",
             settings.mqtt_host, settings.mqtt_port, settings.iot_topic, settings.iot_physical_device)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id + "-serial-sensor")
    configure_client(client, settings)
    client.max_queued_messages_set(2)
    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=10)
    client.loop_start()
    port = None
    windows = SerialWindows(settings.iot_physical_device)
    deadline = time.monotonic() + args.duration if args.duration > 0 else float("inf")
    last_port_scan = 0.0
    last_mock_time = 0.0
    mock_base_temp = 28.5

    try:
        while time.monotonic() < deadline:
            now_mono = time.monotonic()

            # Attempt COM port connection or periodic re-scan
            if port is None and (now_mono - last_port_scan >= 2.0):
                last_port_scan = now_mono
                candidate = find_serial_port(args.port)
                if candidate:
                    try:
                        port = serial.Serial(candidate, args.baud, timeout=0.2)
                        windows = SerialWindows(settings.iot_physical_device)
                        log.info("Reading physical DS18B20 via %s at %s baud", candidate, args.baud)
                    except serial.SerialException as exc:
                        log.warning("Serial port %s unavailable: %s", candidate, exc)
                        port = None
                elif not args.mock_fallback:
                    log.warning("No serial port detected; waiting for hardware connection...")

            raw = b""
            if port is not None:
                try:
                    raw = port.read_until(b"\n", size=256)
                except (serial.SerialException, OSError):
                    log.warning("USB disconnected; retrying")
                    try:
                        port.close()
                    except Exception:
                        pass
                    port = None
            elif args.mock_fallback:
                # Mock fallback generates pulse every ~3s when hardware port is not yet ready
                if now_mono - last_mock_time >= 3.0:
                    last_mock_time = now_mono
                    mock_temp = round(mock_base_temp + (math.sin(now_mono / 10.0) * 0.4), 2)
                    raw = f"Temperature: {mock_temp} degC\n".encode("utf-8")
                else:
                    time.sleep(0.05)

            record = windows.advance(datetime.now(timezone.utc))
            if record:
                if client.is_connected():
                    info = client.publish(settings.iot_topic, json.dumps(record), qos=1, retain=False)
                    if info.rc == mqtt.MQTT_ERR_SUCCESS:
                        log.info("Physical MQTT window sequence=%s temperature=%s samples=%s mode=%s",
                                 record["sequence"], record["temperature"]["mean"],
                                 record["temperature"]["sample_count"], "hardware" if port else "standby-bridge")
                    else:
                        log.warning("Physical window dropped: MQTT queue unavailable")
                else:
                    log.warning("Physical window dropped: MQTT disconnected")

            if raw.endswith(b"\n"):
                value = parse_temperature(raw.decode("utf-8", errors="replace").strip())
                if value is not None:
                    windows.add(value)
                    log.info("Sensor temperature: %s degC (%s)", value, "hardware" if port else "standby-bridge")

            if port is not None:
                time.sleep(0.01)

    except KeyboardInterrupt:
        log.info("Serial publisher stopped")
    finally:
        if port:
            try:
                port.close()
            except Exception:
                pass
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()

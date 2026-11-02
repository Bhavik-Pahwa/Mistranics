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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = Settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id + "-serial-sensor")
    configure_client(client, settings)
    client.max_queued_messages_set(2)
    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=10)
    client.loop_start()
    port = None
    windows = SerialWindows(settings.iot_physical_device)
    deadline = time.monotonic() + args.duration if args.duration > 0 else float("inf")
    try:
        while time.monotonic() < deadline:
            if port is None:
                try:
                    port = serial.Serial(args.port, args.baud, timeout=0.2)
                    windows = SerialWindows(settings.iot_physical_device)
                    log.info("Reading physical DS18B20 via %s at %s baud", args.port, args.baud)
                except serial.SerialException as exc:
                    log.warning("Serial unavailable (close Arduino Serial Monitor): %s", exc)
                    time.sleep(2)
                    continue
            try:
                raw = port.read_until(b"\n", size=256)
                record = windows.advance(datetime.now(timezone.utc))
                if record:
                    if client.is_connected():
                        info = client.publish(settings.iot_topic, json.dumps(record), qos=1, retain=False)
                        if info.rc == mqtt.MQTT_ERR_SUCCESS:
                            log.info("Physical MQTT window sequence=%s temperature=%s samples=%s",
                                     record["sequence"], record["temperature"]["mean"], record["temperature"]["sample_count"])
                        else:
                            log.warning("Physical window dropped: MQTT queue unavailable")
                    else:
                        log.warning("Physical window dropped: MQTT disconnected")
                if raw.endswith(b"\n"):
                    value = parse_temperature(raw.decode("utf-8", errors="replace").strip())
                    if value is not None:
                        windows.add(value)
                        log.info("Actual serial temperature: %s degC", value)
            except (serial.SerialException, OSError):
                log.warning("USB disconnected; retrying")
                port.close()
                port = None
    except KeyboardInterrupt:
        log.info("Serial publisher stopped")
    finally:
        if port:
            port.close()
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()

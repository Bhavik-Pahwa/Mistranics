"""Publish the existing motor simulation via MQTT, never via an HTTP ingestion route.

Run at repository root: python -m backend.examples.iot_simulator --steps 10 --with-anomaly
"""
import argparse
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

from ML.simulation import motor_temperature
from backend.app.config import Settings
from backend.app.mqtt import configure_client
from backend.app.telemetry import Window

log = logging.getLogger(__name__)


def make_window(samples, start, sequence, device_id):
    record = dict(schema_version=1, device_id=device_id, source="simulation", sequence=sequence,
                  window_start=start.isoformat(), window_end=(start + timedelta(seconds=3)).isoformat(),
                  window_duration_seconds=3,
                  temperature=dict(mean=sum(samples) / len(samples), min=min(samples), max=max(samples),
                                   unit="degC", sample_count=len(samples), status="valid"))
    Window.model_validate(record)
    return record


def main():
    parser = argparse.ArgumentParser(description="Existing INDUX motor simulation → MQTT")
    parser.add_argument("--steps", type=int, default=10, help="Three-second windows; 0 runs until Ctrl+C")
    parser.add_argument("--with-anomaly", action="store_true", help="Existing unusual condition in final three windows")
    parser.add_argument("--condition", choices=["normal", "unusual"], default="normal")
    args = parser.parse_args()
    if args.steps < 0 or (args.with_anomaly and args.steps < 8):
        parser.error("Use nonnegative steps, and at least 8 steps with --with-anomaly")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = Settings()
    connected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"indux-simulator-{time.time_ns()}")
    configure_client(client, settings)

    def on_connect(client, userdata, flags, reason, properties):
        if reason == 0:
            connected.set()
            log.info("Simulation MQTT connected")

    def on_disconnect(*_):
        connected.clear()
        log.warning("Simulation broker disconnected; retrying, offline windows will be dropped")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_connect_fail = lambda *_: log.warning("Simulation broker unavailable; retrying")
    client.max_queued_messages_set(2)
    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=10)
    client.loop_start()
    sequence = time.time_ns() // 1000
    step = 0
    try:
        while not connected.wait(1):
            pass
        while args.steps == 0 or step < args.steps:
            start = datetime.now(timezone.utc)
            clock = time.monotonic()
            samples = []
            for sample in range(3):
                time.sleep(max(0, clock + sample - time.monotonic()))
                samples.append(motor_temperature(step, args.steps, args.with_anomaly)
                               if args.condition == "normal" else motor_temperature(0, 3, True))
            time.sleep(max(0, clock + 3 - time.monotonic()))
            sequence += 1
            record = make_window(samples, start, sequence, settings.iot_simulation_device)
            if connected.is_set():
                info = client.publish(settings.iot_topic, json.dumps(record), qos=1, retain=False)
                try:
                    info.wait_for_publish(timeout=2)
                    log.info("Simulation window=%s temperature=%.2f acknowledged=%s", step + 1,
                             record["temperature"]["mean"], info.is_published())
                except (RuntimeError, ValueError):
                    log.warning("Simulation publish interrupted; MQTT reconnect will retry queued QoS 1")
            else:
                log.warning("Dropped offline simulation window=%s", step + 1)
            step += 1
    except KeyboardInterrupt:
        log.info("Simulation stopped")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()

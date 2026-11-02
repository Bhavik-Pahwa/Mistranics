"""Publish real MQTT telemetry, submit mocked external detector output, verify incident."""

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
import httpx
import paho.mqtt.client as mqtt
from app.config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    config = Settings()
    window = "demo-" + str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    telemetry = {
        "schema_version": "1.0",
        "machine_id": "motor_001",
        "device_id": "esp32_001",
        "reading_id": window,
        "measured_at": timestamp,
        "readings": [
            {
                "sensor_id": "temp_01",
                "parameter": "motor_temperature",
                "value": 56.4,
                "unit": "degC",
            }
        ],
    }
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)
    if config.mqtt_tls:
        client.tls_set(config.mqtt_ca, config.mqtt_cert, config.mqtt_key)
    client.connect(config.mqtt_host, config.mqtt_port)
    client.loop_start()
    try:
        for _ in range(2):
            client.publish(
                "mistranics/motor_001/telemetry", json.dumps(telemetry), qos=1
            ).wait_for_publish(timeout=10)
    finally:
        client.disconnect()
        client.loop_stop()
    headers = (
        {"Authorization": "Bearer " + config.api_token} if config.api_token else {}
    )
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=10) as api:
        deadline = time.monotonic() + 20
        while True:
            response = api.get("/api/v1/assets/motor_001/readings/latest")
            if response.status_code == 200 and response.json()["window_id"] == window:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "MQTT telemetry not persisted; check subscription/configuration"
                )
            time.sleep(0.2)
        for kind in ["manufacturer_limits", "statistical", "isolation_forest"]:
            result = {
                "schema_version": "1.0",
                "machine_id": "motor_001",
                "window_id": window,
                "run_id": str(uuid.uuid4()),
                "detector": kind,
                "evaluated_at": timestamp,
                "status": "completed",
                "data_quality": {"status": "valid", "warnings": []},
                "model_or_config_version": "demo-v1",
                "findings": [],
            }
            if kind == "isolation_forest":
                result.update(
                    model_version="demo-model", feature_schema_version="demo-features"
                )
            else:
                result["config_version"] = "demo-config"
            if kind == "manufacturer_limits":
                result["findings"] = [
                    {
                        "kind": "machine_condition",
                        "verified": True,
                        "limit_category": "critical",
                        "source": "MOCK DEMO",
                    }
                ]
            response = api.post(
                "/api/v1/internal/detector-results",
                headers={"Authorization": "Bearer " + config.internal_token},
                json=result,
            )
            response.raise_for_status()
        deadline = time.monotonic() + 20
        while True:
            response = api.get("/api/v1/assets/motor_001/anomalies")
            response.raise_for_status()
            decisions = [
                d for d in response.json()["items"] if d["window_id"] == window
            ]
            if decisions:
                assert decisions[0]["final_status"] == "anomaly", decisions[0]
                break
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "Decision missing: demo requires POLICY_FILE=examples/demo-policy.json"
                )
            time.sleep(0.2)
        response = api.get(
            "/api/v1/alerts", params={"asset_id": "motor_001", "status": "active"}
        )
        response.raise_for_status()
        assert response.json()["items"], "Expected active demo incident"
        print(
            json.dumps(
                {
                    "window_id": window,
                    "decision_id": decisions[0]["id"],
                    "alerts": response.json()["items"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

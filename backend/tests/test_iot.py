import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.telemetry import RollingZScore, TelemetryState, Window


def settings(**kwargs):
    return Settings(_env_file=None, iot_enabled=True, mqtt_enabled=False, **kwargs)


def payload(sequence=1, source="physical", value=32.0, end=None):
    end = end or datetime.now(timezone.utc)
    return dict(schema_version=1, device_id="device-01" if source == "physical" else "simulation-01",
                source=source, sequence=sequence, window_start=(end - timedelta(seconds=3)).isoformat(),
                window_end=end.isoformat(), window_duration_seconds=3,
                temperature=dict(mean=value, min=value, max=value, unit="degC", sample_count=3, status="valid"))


def test_ingestion_and_source_switch():
    state = TelemetryState(settings())
    state.connected(True)
    first = payload()
    state.consume(first)
    state.consume(first)
    assert len(state.history) == 1
    assert state.latest["anomaly"]["status"] == "WARMING_UP"
    state.select("simulation")
    assert state.snapshot()["latest"] is None
    assert not state.history and not state.detector.values
    state.consume(first)
    assert not state.history
    state.consume(payload(source="simulation"))
    assert state.latest["source"] == "simulation"
    state.select("physical")
    state.consume(first)
    assert not state.history  # Switching does not forget QoS duplicate identities.


@pytest.mark.parametrize("field,value", [("mean", float("nan")), ("max", float("inf")),
    ("mean", "32"), ("sample_count", True), ("sample_count", 0), ("mean", 126),
    ("min", 40), ("unit", "F"), ("status", "unknown")])
def test_invalid_temperature(field, value):
    record = payload()
    record["temperature"][field] = value
    with pytest.raises(ValidationError):
        Window.model_validate(record)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("sequence", -1),
    ("source", "other"), ("window_start", "2026-01-01T00:00:00"),
    ("window_duration_seconds", 6), ("device_id", "")])
def test_invalid_envelope(field, value):
    record = payload()
    record[field] = value
    with pytest.raises(ValidationError):
        Window.model_validate(record)


def test_error_and_stale_are_distinct_from_mqtt():
    state = TelemetryState(settings())
    state.connected(True)
    record = payload()
    record["temperature"].update(mean=None, min=None, max=None, sample_count=0, status="disconnected")
    state.consume(record)
    assert state.snapshot()["stream_status"] == "SENSOR_ERROR"
    assert not state.detector.values
    assert state.latest["anomaly"]["z_score"] is None
    state.last_received_monotonic -= 11
    assert state.snapshot()["stream_status"] == "DISCONNECTED"
    assert state.snapshot()["mqtt_connected"] is True


def test_detector_previous_samples_and_bounds():
    detector = RollingZScore(settings())
    for value in [32, 32.1, 31.9, 32.1, 31.9]:
        assert detector.evaluate(value)["status"] == "WARMING_UP"
    assert detector.evaluate(32)["status"] == "NORMAL"
    result = detector.evaluate(48)
    assert result["status"] == "ANOMALY"
    assert result["baseline_mean"] == pytest.approx(32)
    assert result["z_score"] == pytest.approx(160)
    for _ in range(100):
        detector.evaluate(32)
    assert len(detector.values) == 20
    assert detector.evaluate(33)["status"] == "ANOMALY"


def test_config_and_exact_threshold():
    with pytest.raises(ValueError):
        RollingZScore(settings(anomaly_min_baseline_samples=21))
    detector = RollingZScore(settings(anomaly_std_floor=1))
    for _ in range(5):
        detector.evaluate(32)
    assert detector.evaluate(35)["status"] == "ANOMALY"


def test_old_future_wrong_device_overlap():
    state = TelemetryState(settings())
    for record in [payload(end=datetime.now(timezone.utc) - timedelta(seconds=30)),
                   payload(end=datetime.now(timezone.utc) + timedelta(seconds=30)),
                   payload() | {"device_id": "unknown"}]:
        with pytest.raises(ValueError):
            state.consume(record)
    first = payload()
    state.consume(first)
    with pytest.raises(ValueError):
        state.consume(first | {"sequence": 2})


def test_history_bounded():
    state = TelemetryState(settings(telemetry_stale_after_seconds=300))
    start = datetime.now(timezone.utc) - timedelta(seconds=240)
    state.selected_at = start - timedelta(seconds=10)
    for i in range(70):
        state.consume(payload(i + 1, end=start + timedelta(seconds=i * 3)))
    assert len(state.history) == 60
    assert len(state.detector.values) == 20
    assert len(state.sequences) == 1


def test_api_websocket_and_reconnect_no_database():
    app = create_app(settings(database_url="invalid://should-never-open"))
    with TestClient(app) as client:
        assert client.get("/health").json()["mode"] == "iot"
        assert client.post("/api/source", json={"source": "bad"}).status_code == 422
        with client.websocket_connect("/ws/telemetry") as ws:
            assert ws.receive_json()["latest"] is None
            app.state.telemetry.consume(payload())
            assert ws.receive_json()["latest"]["temperature"] == 32
        with client.websocket_connect("/ws/telemetry") as ws:
            assert len(ws.receive_json()["history"]) == 1
            switched = client.post("/api/source", json={"source": "simulation"}).json()
            assert switched["latest"] is None
            assert ws.receive_json()["source"] == "simulation"


def test_server_simulator_api_and_stream():
    with TestClient(create_app(settings())) as client:
        state = client.get("/api/simulation").json()
        assert state["type"] == "simulation_state"
        assert len(state["waveforms"]["ax"]) == 400
        assert state["publisher_enabled"]
        for changes in [{"rpm": 4000}, {"severity": -1}, {"mode": "bad"}, {"rpm": "1500"}, {"source": "physical"}]:
            assert client.patch("/api/simulation", json=changes).status_code == 422
        response = client.patch("/api/simulation", json={"mode": "heat", "rpm": 2200, "paused": True}).json()
        assert response["mode"] == "heat" and response["rpm"] == 2200
        assert client.post("/api/simulation/cool-down").json()["temperature"] == 28
        with client.websocket_connect("/ws/simulation") as ws:
            assert ws.receive_json()["paused"] is True
        assert client.get("/api/simulation").json()["paused"] is True
        html = client.get("/simulator").text
        assert "frontend.js" in html and "function sample()" not in html
        assert "/api/simulation" in client.get("/openapi.json").json()["paths"]


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for integration state")


@pytest.mark.skipif(not os.getenv("RUN_MQTT_TESTS"), reason="Set RUN_MQTT_TESTS=1 for real Mosquitto integration")
def test_real_mqtt_ingestion_reconnect(tmp_path):
    executable = shutil.which("mosquitto")
    assert executable, "Install Mosquitto and add it to PATH"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = tmp_path / "mosquitto.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")

    def broker():
        return subprocess.Popen([executable, "-c", str(config)], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

    process = broker()
    cfg = settings(simulator_publish_enabled=False, mqtt_host="127.0.0.1", mqtt_port=port, mqtt_client_id="indux-test", mqtt_reconnect_max=2)
    cfg.mqtt_enabled = True
    app = create_app(cfg)
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        with TestClient(app) as client:
            wait_for(lambda: client.get("/api/status").json()["mqtt_connected"])
            publisher.connect("127.0.0.1", port)
            publisher.loop_start()
            for raw in ["{bad json", json.dumps(payload() | {"source": "bad"}),
                        json.dumps(payload() | {"temperature": {"mean": "invalid"}})]:
                publisher.publish(cfg.iot_topic, raw, qos=1).wait_for_publish(3)
            record = payload()
            publisher.publish(cfg.iot_topic, json.dumps(record), qos=1).wait_for_publish(3)
            wait_for(lambda: client.get("/api/status").json()["latest"] is not None)
            publisher.publish(cfg.iot_topic, json.dumps(record), qos=1).wait_for_publish(3)
            time.sleep(0.2)
            assert len(client.get("/api/status").json()["history"]) == 1
            process.terminate()
            process.wait(timeout=5)
            wait_for(lambda: not client.get("/api/status").json()["mqtt_connected"])
            process = broker()
            wait_for(lambda: client.get("/api/status").json()["mqtt_connected"])
            wait_for(publisher.is_connected)
            client.post("/api/source", json={"source": "simulation"})
            publisher.publish(cfg.iot_topic, json.dumps(payload(source="simulation")), qos=1).wait_for_publish(3)
            wait_for(lambda: client.get("/api/status").json()["latest"] is not None)
            assert client.get("/api/status").json()["latest"]["source"] == "simulation"
            client.post("/api/source", json={"source": "physical"})
            client.post("/api/source", json={"source": "simulation"})
            result = subprocess.run(
                [sys.executable, "-m", "backend.examples.iot_simulator", "--steps", "10", "--with-anomaly"],
                cwd=Path(__file__).resolve().parents[2],
                env=os.environ | {"MQTT_HOST": "127.0.0.1", "MQTT_PORT": str(port)},
                capture_output=True, text=True, timeout=40,
            )
            assert result.returncode == 0, result.stderr
            wait_for(lambda: len(client.get("/api/status").json()["history"]) == 10)
            history = client.get("/api/status").json()["history"]
            assert all(p["source"] == "simulation" and p["sample_count"] == 3 for p in history)
            assert [p["anomaly"]["status"] for p in history[:5]] == ["WARMING_UP"] * 5
            assert history[5]["anomaly"]["status"] == "NORMAL"
            assert history[7]["anomaly"]["status"] == "ANOMALY"
            client.patch("/api/simulation", json={"publisher_enabled": True, "mode": "heat"})
            previous = client.get("/api/status").json()["latest"]["sequence"]
            wait_for(lambda: client.get("/api/status").json()["latest"]["sequence"] > previous)
            server_window = client.get("/api/status").json()["latest"]
            assert server_window["source"] == "simulation" and server_window["sample_count"] == 3
            wait_for(lambda: client.get("/api/simulation").json()["published_windows"] > 0)
            process.terminate()
            process.wait(timeout=5)
            wait_for(lambda: not client.get("/api/simulation").json()["mqtt_connected"])
            process = broker()
            wait_for(lambda: client.get("/api/simulation").json()["mqtt_connected"])
            previous = server_window["sequence"]
            wait_for(lambda: client.get("/api/status").json()["latest"]["sequence"] > previous)
            client.patch("/api/simulation", json={"publisher_enabled": False})
    finally:
        publisher.disconnect()
        publisher.loop_stop()
        process.terminate()
        process.wait(timeout=5)

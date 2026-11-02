"""Real service test: enable with TEST_DATABASE_URL and TEST_MQTT_PORT."""

import json
import os
import time
import uuid
import pytest
import paho.mqtt.client as mqtt
from sqlalchemy import select, func, text, inspect
from app.config import Settings
from app.db import Base, Reading
from app.manage import migrate
from app.mqtt import Subscriber
from app.services import process_pending
from conftest import detector


def wait_until(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Service condition did not become true")


def test_versioned_migrations(app):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-only migration test")
    Base.metadata.drop_all(app.state.engine)
    with app.state.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS schema_migrations"))
    migrate(app.state.engine)
    migrate(app.state.engine)
    assert set(Base.metadata.tables) <= set(inspect(app.state.engine).get_table_names())
    with app.state.engine.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM schema_migrations")) == 2


def test_real_mqtt_to_alert(app, client, telemetry):
    if app.state.engine.dialect.name != "postgresql" or not os.getenv("TEST_MQTT_PORT"):
        pytest.skip("Requires disposable PostgreSQL and external MQTT broker")
    settings = Settings(
        mqtt_port=int(os.environ["TEST_MQTT_PORT"]),
        mqtt_host=os.getenv("TEST_MQTT_HOST", "127.0.0.1"),
        mqtt_client_id="test-" + str(uuid.uuid4()),
        mqtt_topic="tests/telemetry",
        retry_seconds=1,
    )
    subscriber = Subscriber(settings, app.state.factory)
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.start()
    publisher.connect(settings.mqtt_host, settings.mqtt_port)
    publisher.loop_start()
    try:
        wait_until(lambda: subscriber.client.is_connected())
        time.sleep(0.2)  # allow SUBACK before publishing
        publisher.publish("tests/telemetry", b"{invalid", qos=1).wait_for_publish()
        publisher.publish(
            "tests/telemetry", json.dumps(telemetry), qos=1
        ).wait_for_publish()

        def count_readings():
            with app.state.factory() as session:
                return session.scalar(select(func.count()).select_from(Reading))

        wait_until(lambda: count_readings() == 1)
        publisher.publish(
            "tests/telemetry", json.dumps(telemetry), qos=1
        ).wait_for_publish()
        later = telemetry | {
            "reading_id": "later",
            "measured_at": "2026-11-02T09:10:06Z",
        }
        publisher.publish(
            "tests/telemetry", json.dumps(later), qos=1
        ).wait_for_publish()
        wait_until(lambda: count_readings() == 2)
        for kind in ["manufacturer_limits", "statistical", "isolation_forest"]:
            findings = (
                [
                    {
                        "kind": "machine_condition",
                        "verified": True,
                        "limit_category": "critical",
                    }
                ]
                if kind == "manufacturer_limits"
                else []
            )
            response = client.post(
                "/api/v1/internal/detector-results",
                headers={"Authorization": "Bearer internal"},
                json=detector(kind, findings=findings),
            )
            assert response.status_code == 200
        process_pending(app.state.factory, app.state.policy)
        alerts = client.get("/api/v1/alerts").json()["items"]
        assert len(alerts) == 1
        decision = client.get("/api/v1/anomalies/" + alerts[0]["decision_id"]).json()
        assert decision["final_status"] == "anomaly"
        assert len(decision["evidence"]) == 3
        # Simulate disconnect and reconnect using the same persistent subscription.
        subscriber.client.disconnect()
        subscriber.client.reconnect()
        subscriber.client.loop_start()
        wait_until(lambda: subscriber.client.is_connected())
        time.sleep(0.2)
        publisher.publish(
            "tests/telemetry",
            json.dumps(telemetry | {"reading_id": "reconnected"}),
            qos=1,
        ).wait_for_publish()
        wait_until(lambda: count_readings() == 3)
    finally:
        publisher.disconnect()
        publisher.loop_stop()
        subscriber.stop()

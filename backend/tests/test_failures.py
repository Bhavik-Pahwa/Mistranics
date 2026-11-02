from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from app.config import Settings
from app.db import Reading, Decision, Alert
from app.mqtt import Subscriber
from app.schemas import Telemetry
from app.services import (
    ingest,
    accept_result,
    evaluate,
    process_pending,
    transition,
    DomainError,
    register_policy,
)
from conftest import detector


def test_policy_version_immutable(app):
    with app.state.factory.begin() as session:
        register_policy(session, app.state.policy)
    with (
        app.state.factory.begin() as session,
        pytest.raises(ValueError, match="immutable"),
    ):
        register_policy(
            session, app.state.policy.model_copy(update={"timeout_seconds": 31})
        )


def test_mqtt_database_retry_and_malformed_isolation(app, telemetry):
    import json

    factory = Mock()
    factory.begin.side_effect = [
        RuntimeError("database unavailable"),
        app.state.factory.begin(),
    ]
    subscriber = Subscriber(Settings(retry_seconds=0), factory)
    subscriber.client.ack = Mock(side_effect=lambda *args: subscriber.stop_event.set())
    message = SimpleNamespace(payload=json.dumps(telemetry).encode(), mid=1, qos=1)
    subscriber.messages.put(message)
    subscriber.run()
    assert factory.begin.call_count == 2
    subscriber.client.ack.assert_called_once_with(1, 1)
    with app.state.factory() as session:
        assert session.scalar(select(func.count()).select_from(Reading)) == 1


def test_nested_nonfinite_and_out_of_range(app, telemetry):
    from pydantic import ValidationError

    telemetry["operating_context"] = {"rpm": float("nan")}
    with pytest.raises(ValidationError):
        Telemetry.model_validate(telemetry)
    telemetry["operating_context"] = {}
    telemetry["readings"][0]["quality"] = "out_of_range"
    with app.state.factory.begin() as session:
        row, _ = ingest(session, telemetry)
        assert row.readings[0]["quality"] == "out_of_range"


def test_active_incident_grouping_and_resolution_guard(app, telemetry):
    policy = app.state.policy.model_copy(update={"resolve_on_normal": True})
    with app.state.factory.begin() as session:

        def observation(window, measured, anomalous):
            row, _ = ingest(
                session, telemetry | {"reading_id": window, "measured_at": measured}
            )
            for kind in policy.required_detectors:
                findings = (
                    [
                        {
                            "kind": "machine_condition",
                            "verified": True,
                            "limit_category": "critical",
                        }
                    ]
                    if anomalous and kind == "manufacturer_limits"
                    else []
                )
                accept_result(
                    session, detector(kind, window_id=window, findings=findings)
                )
            return evaluate(session, row, policy)

        observation("first", "2026-11-02T09:10:03Z", True)
        observation("newer", "2026-11-02T09:10:09Z", True)
        observation("late-normal", "2026-11-02T09:10:06Z", False)
        alert = session.scalar(select(Alert))
        assert alert.status == "active"
        assert session.scalar(select(func.count()).select_from(Alert)) == 1
        with pytest.raises(DomainError, match="unavailable"):
            transition(session, alert.id, "resolve", "test", None)
        with pytest.raises(DomainError):
            transition(
                session,
                alert.id,
                "resolve",
                "test",
                policy.model_copy(update={"manual_resolution": False}),
            )
        observation("recovery", "2026-11-02T09:10:12Z", False)
        assert alert.status == "resolved"


def test_retry_from_persisted_results(app, telemetry):
    with app.state.factory.begin() as session:
        ingest(session, telemetry)
        for kind in app.state.policy.required_detectors:
            accept_result(session, detector(kind))
    process_pending(app.state.factory, app.state.policy)
    process_pending(app.state.factory, app.state.policy)
    with app.state.factory() as session:
        assert session.scalar(select(func.count()).select_from(Decision)) == 1


def test_api_database_failure(app, client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    original = app.state.engine.dialect.do_execute

    def fail(cursor, statement, parameters, context=None):
        if "sensor_readings" in statement:
            raise OperationalError(
                statement, None, Exception("simulated database outage")
            )
        return original(cursor, statement, parameters, context)

    monkeypatch.setattr(app.state.engine.dialect, "do_execute", fail)
    response = client.get("/api/v1/assets/motor_001/readings/latest")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable or operation failed"}


def test_findings_require_exact_typed_match(app, telemetry):
    with app.state.factory.begin() as session:
        row, _ = ingest(session, telemetry)
        for kind in app.state.policy.required_detectors:
            findings = (
                [
                    {
                        "kind": "machine_condition",
                        "verified": 1,
                        "limit_category": "critical",
                    }
                ]
                if kind == "manufacturer_limits"
                else []
            )
            accept_result(session, detector(kind, findings=findings))
        assert evaluate(session, row, app.state.policy).final_status == "indeterminate"


def test_concurrent_redelivery(app, telemetry):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Row locking requires PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor

    def write(_):
        with app.state.factory.begin() as session:
            row, duplicate = ingest(session, telemetry)
            return row.id, duplicate

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(write, range(4)))
    assert len({result[0] for result in results}) == 1
    assert sum(not result[1] for result in results) == 1


def test_unreliable_source_telemetry_cannot_be_normal(app, telemetry):
    telemetry["readings"][0].update(value=None, quality="missing")
    with app.state.factory.begin() as session:
        row, _ = ingest(session, telemetry)
        for kind in app.state.policy.required_detectors:
            accept_result(session, detector(kind))
        decision = evaluate(session, row, app.state.policy)
        assert decision.final_status == "indeterminate"
        assert decision.decision_reason["rule_id"] == "telemetry_quality"

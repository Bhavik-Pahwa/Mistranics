import copy
from datetime import timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from app.schemas import Telemetry, DetectorResult
from app.db import Reading, Result, Decision, Alert, now
from app.services import ingest, accept_result, evaluate, process_pending, DomainError
from conftest import detector


@pytest.mark.parametrize(
    "change",
    [
        {"machine_id": ""},
        {"schema_version": "2.0"},
        {"measured_at": "2026-11-02T09:10:03"},
        {"window_start": "2026-11-03T00:00:00Z"},
        {"readings": []},
    ],
)
def test_invalid_envelopes(telemetry, change):
    with pytest.raises(ValidationError):
        Telemetry.model_validate(telemetry | change)


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), "2", True, None]
)
def test_invalid_values(telemetry, value):
    telemetry["readings"][0]["value"] = value
    with pytest.raises(ValidationError):
        Telemetry.model_validate(telemetry)


def test_utc_quality(telemetry):
    telemetry["measured_at"] = "2026-11-02T14:40:03+05:30"
    telemetry["readings"][0].update(value=None, quality="missing")
    result = Telemetry.model_validate(telemetry)
    assert result.measured_at.hour == 9
    assert (result.window_end - result.window_start).total_seconds() == 3


def test_canonical_dedup_unknown_units(app, telemetry):
    with app.state.factory.begin() as session:
        row, duplicate = ingest(session, telemetry)
        assert not duplicate
        assert row.readings[0]["value_original"] == 56.4
        assert row.readings[0]["value_normalized"] == 56.4
        assert ingest(session, telemetry)[1]
        changed = copy.deepcopy(telemetry)
        changed["readings"][0]["value"] = 99
        with pytest.raises(DomainError, match="different content"):
            ingest(session, changed)
        telemetry["reading_id"] = "window-2"
        telemetry["readings"][0]["unit"] = "unknown"
        row, _ = ingest(session, telemetry)
        assert row.readings[0]["quality"] == "suspect"
        assert row.readings[0]["value_normalized"] is None
        telemetry["reading_id"] = "window-3"
        telemetry["readings"][0].update(value=None, quality="missing")
        row, _ = ingest(session, telemetry)
        assert row.readings[0]["quality"] == "missing"


def test_conversion_and_registry(app, telemetry):
    from app.db import Asset

    with app.state.factory.begin() as session:
        asset = session.get(Asset, "motor_001")
        cfg = copy.deepcopy(asset.metadata_json)
        cfg["sensors"][0]["units"]["degF"] = {
            "canonical_unit": "degC",
            "scale": 5 / 9,
            "offset": -32 * 5 / 9,
        }
        asset.metadata_json = cfg
        telemetry["readings"][0].update(value=212.0, unit="degF")
        row, _ = ingest(session, telemetry)
        assert row.readings[0]["value_normalized"] == pytest.approx(100)
    for change in [{"machine_id": "unknown"}, {"device_id": "unknown"}]:
        with app.state.factory.begin() as session, pytest.raises(DomainError):
            ingest(session, telemetry | change)


def test_event_time_api(app, client, telemetry):
    with app.state.factory.begin() as session:
        for i in [20, 0, 10]:
            item = telemetry | {
                "reading_id": f"window-{i}",
                "measured_at": f"2026-11-02T09:10:{i:02}Z",
            }
            ingest(session, item)
    query = "?start=2026-11-02T09:09:30Z&end=2026-11-02T09:10:30Z&limit=2"
    response = client.get("/api/v1/assets/motor_001/readings" + query)
    assert response.status_code == 200
    data = response.json()
    assert [r["window_id"] for r in data["items"]] == ["window-0", "window-10"]
    assert data["next_offset"] == 2
    assert (
        client.get("/api/v1/assets/motor_001/readings/latest").json()["window_id"]
        == "window-20"
    )
    assert client.get("/api/v1/assets/motor_001/readings?limit=1001").status_code == 422
    assert (
        client.get(
            "/api/v1/assets/motor_001/readings?start=2020-01-01T00:00:00Z"
        ).status_code
        == 422
    )
    assert client.get("/api/v1/assets/unknown/readings").status_code == 404
    assert (
        client.get(
            "/api/v1/assets/motor_001/readings?start=2026-11-02T09:00:00"
        ).status_code
        == 422
    )


def test_result_validation():
    for kind in ["manufacturer_limits", "statistical", "isolation_forest"]:
        assert DetectorResult.model_validate(detector(kind)).detector == kind
    for changes in [{"detector": "unknown"}, {"run_id": ""}, {"status": "normal"}]:
        with pytest.raises(ValidationError):
            DetectorResult.model_validate(detector(**changes))
    bad = detector("isolation_forest")
    bad.pop("model_version")
    with pytest.raises(ValidationError):
        DetectorResult.model_validate(bad)


def test_results_protected_and_idempotent(app, client, telemetry):
    with app.state.factory.begin() as session:
        ingest(session, telemetry)
    url = "/api/v1/internal/detector-results"
    assert client.post(url, json=detector()).status_code == 401
    auth = {"Authorization": "Bearer internal"}
    first = client.post(url, json=detector(), headers=auth)
    assert first.status_code == 200
    assert not first.json()["duplicate"]
    assert client.post(url, json=detector(), headers=auth).json()["duplicate"]
    assert (
        client.post(
            url, json=detector(status="invalid_input"), headers=auth
        ).status_code
        == 409
    )
    assert (
        client.post(url, json=detector(window_id="absent"), headers=auth).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/detector-results/" + first.json()["result"]["id"]
        ).status_code
        == 200
    )


def add_results(session, failure=None, findings=None):
    for kind in ["manufacturer_limits", "statistical", "isolation_forest"]:
        accept_result(
            session,
            detector(
                kind,
                status=failure
                if failure and kind == "isolation_forest"
                else "completed",
                findings=findings if findings and kind == "manufacturer_limits" else [],
            ),
        )


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "insufficient_data",
        "invalid_input",
        "model_unavailable",
        "processing_error",
    ],
)
def test_decision_statuses(app, telemetry, failure):
    with app.state.factory.begin() as session:
        reading, _ = ingest(session, telemetry)
        add_results(session, failure)
        decision = evaluate(session, reading, app.state.policy)
        assert decision.final_status == (
            "normal" if failure is None else "indeterminate"
        )
        assert len(decision.evidence) == 3
        assert all(session.get(Result, e["result_id"]) for e in decision.evidence)


def test_critical_not_vetoed_alert_lifecycle(app, client, telemetry):
    with app.state.factory.begin() as session:
        reading, _ = ingest(session, telemetry)
        add_results(
            session,
            findings=[
                {
                    "kind": "machine_condition",
                    "verified": True,
                    "limit_category": "critical",
                    "source": "manual-x",
                }
            ],
        )
        decision = evaluate(session, reading, app.state.policy)
        assert decision.final_status == "anomaly"
        assert evaluate(session, reading, app.state.policy).id == decision.id
    process_pending(app.state.factory, app.state.policy)
    items = client.get("/api/v1/alerts").json()["items"]
    assert len(items) == 1
    alert_id = items[0]["id"]
    url = "/api/v1/alerts/" + alert_id
    assert (
        client.post(url + "/acknowledge", json={"reason": "reviewed"}).status_code
        == 401
    )
    auth = {"Authorization": "Bearer operator"}
    assert (
        client.post(
            url + "/acknowledge", json={"reason": "reviewed"}, headers=auth
        ).json()["status"]
        == "acknowledged"
    )
    assert (
        client.post(
            url + "/acknowledge", json={"reason": "again"}, headers=auth
        ).status_code
        == 409
    )
    assert (
        client.post(
            url + "/resolve", json={"reason": "inspection complete"}, headers=auth
        ).json()["status"]
        == "resolved"
    )
    assert (
        client.post(
            url + "/resolve", json={"reason": "again"}, headers=auth
        ).status_code
        == 409
    )
    assert [e["event_type"] for e in client.get(url).json()["events"]["items"]] == [
        "created",
        "acknowledged",
        "resolved",
    ]
    assert client.get("/api/v1/anomalies/" + decision.id).status_code == 200
    assert client.get("/api/v1/assets/motor_001/diagnostic-context").status_code == 200


def test_missing_timeout_and_late_results(app, telemetry):
    with app.state.factory.begin() as session:
        reading, _ = ingest(session, telemetry)
        assert evaluate(session, reading, app.state.policy) is None
        reading.ingested_at = now() - timedelta(seconds=60)
        result = evaluate(session, reading, app.state.policy)
        assert result.final_status == "indeterminate"
        assert len(result.evidence) == 0
        add_results(session)
        assert evaluate(session, reading, app.state.policy).id == result.id
        assert result.final_status == "indeterminate"


def test_policy_unavailable(app, telemetry):
    with app.state.factory.begin() as session:
        ingest(session, telemetry)
        add_results(session)
    process_pending(app.state.factory, None)
    with app.state.factory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Decision)) == 0


def test_quality_findings_do_not_alert(app, telemetry):
    with app.state.factory.begin() as session:
        row, _ = ingest(session, telemetry)
        add_results(
            session,
            findings=[
                {"kind": "data_quality", "verified": True, "limit_category": "critical"}
            ],
        )
        result = evaluate(session, row, app.state.policy)
        assert result.final_status == "indeterminate"
        assert session.scalar(select(func.count()).select_from(Alert)) == 0


def test_alert_policy_unavailable(app, telemetry):
    policy = app.state.policy.model_copy(update={"alerts_enabled": False})
    with app.state.factory.begin() as session:
        row, _ = ingest(session, telemetry)
        add_results(
            session,
            findings=[
                {
                    "kind": "machine_condition",
                    "verified": True,
                    "limit_category": "critical",
                }
            ],
        )
        decision = evaluate(session, row, policy)
        assert not decision.alert_processed
        assert session.scalar(select(func.count()).select_from(Alert)) == 0


def test_auth_and_missing(client):
    assert (
        client.get("/api/v1/assets", headers={"Authorization": "wrong"}).status_code
        == 401
    )
    assert client.get("/api/v1/assets").status_code == 200
    assert client.get("/api/v1/assets/absent").status_code == 404
    assert client.get("/api/v1/alerts/absent").status_code == 404


def test_transaction_rollback(app, telemetry):
    with pytest.raises(RuntimeError):
        with app.state.factory.begin() as session:
            ingest(session, telemetry)
            raise RuntimeError("simulated failure")
    with app.state.factory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Reading)) == 0


def test_nonfinite_callback_returns_validation_error(client):
    response = client.post(
        "/api/v1/internal/detector-results",
        headers={
            "Authorization": "Bearer internal",
            "Content-Type": "application/json",
        },
        content='{"data_quality":{"status":"valid","warnings":[]},"findings":[{"score":NaN}]}',
    )
    assert response.status_code == 422

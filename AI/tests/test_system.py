import json
from datetime import timedelta
import pytest
from sqlalchemy import select, func
from backend.app.db import Result, Alert, now
from backend.app.services import ingest
from ML.persistence import AnomalyEvent, ProcessingCheckpoint
from AI.models import Session, Message
from AI.reasoning import validate_answer, InvalidAnswer, SAFETY_WARNING
from AI.rag import retrieve
from AI.provider import ProviderError
from conftest import telemetry, approve_limit

READ = {"Authorization": "Bearer read"}


def start(client, **kwargs):
    response = client.post(
        "/api/v1/troubleshooting/sessions", json={"machine_id": "motor_001", **kwargs}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def ask(app, client, session, text="What is the current temperature?", request="q1"):
    response = client.post(
        f"/api/v1/troubleshooting/sessions/{session}/messages",
        json={"request_id": request, "text": text},
    )
    assert response.status_code == 202, response.text
    app.state.troubleshooting.process_one(app.state.factory)
    return client.get(
        f"/api/v1/troubleshooting/sessions/{session}", headers=READ
    ).json()["messages"]["items"][-1]


def ingest_step(app, window="w1", temperature=80.0, vibration=2.0, at=None):
    with app.state.factory.begin() as db:
        ingest(db, telemetry(window, temperature, vibration, at))
    app.state.classical.step(app.state.factory, True)


def upload(client, pdf, version="v1", doc="manual"):
    return client.post(
        "/api/v1/documents",
        data={
            "document_id": doc,
            "version": version,
            "machine_id": "motor_001",
            "manufacturer": "Test manufacturer",
            "machine_model": "Test model",
        },
        files={"file": ("manual.pdf", pdf, "application/pdf")},
    )


def test_complete_anomaly_to_chat_to_feedback_recovery(system, pdf):
    app, client, fake, settings = system
    approve_limit(app)
    at = now()
    ingest_step(app, at=at)
    ingest_step(app, "w2", 82.0, at=at + timedelta(seconds=3))
    with app.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 1
        incident = db.scalar(select(Alert))
        assert incident.metadata_json["observation_count"] == 2
        assert incident.severity == "warning"
        session = db.scalar(select(Session))
        incident_id, session_id = incident.id, session.id
        assert db.scalar(select(func.count()).select_from(AnomalyEvent)) == 2
        assert db.scalar(select(func.count()).select_from(Result)) == 6
    assert upload(client, pdf).status_code == 201
    assert (
        client.patch(
            f"/api/v1/troubleshooting/sessions/{session_id}/manual",
            json={
                "machine_id": "motor_001",
                "incident_id": incident_id,
                "document_id": "manual",
                "document_version": "v1",
            },
        ).status_code
        == 200
    )
    message = ask(
        app,
        client,
        session_id,
        "Why is pressure increasing and what manual checks apply?",
    )
    assert message["state"] == "completed", message
    assert message["response"]["sources"][0]["page"] == 1
    assert message["response"]["sources"][0]["version"] == "v1"
    assert SAFETY_WARNING in message["response"]["safety_warnings"]
    detail = client.get(
        f"/api/v1/troubleshooting/sessions/{session_id}", headers=READ
    ).json()
    step = detail["steps"]["items"][0]
    response = client.post(
        f"/api/v1/troubleshooting/sessions/{session_id}/feedback",
        json={
            "kind": "step_completed",
            "step_id": step["id"],
            "text": "I replaced the bearing",
        },
    )
    assert response.status_code == 201
    assert response.json()["provenance"] == "operator_reported"
    assert (
        client.get("/api/v1/incidents/" + incident_id, headers=READ).json()["metadata"][
            "condition_state"
        ]
        == "ACTIVE"
    )
    for i in range(3):
        ingest_step(app, "normal-" + str(i), 50.0, at=at + timedelta(seconds=6 + i * 3))
    recovered = client.get("/api/v1/incidents/" + incident_id, headers=READ).json()
    assert recovered["metadata"]["condition_state"] == "RESOLVED"
    # A recurrence within the configured correlation interval reopens the existing incident.
    ingest_step(app, "recurrence", 80.0, at=at + timedelta(seconds=15))
    assert (
        client.get("/api/v1/incidents/" + incident_id, headers=READ).json()["metadata"][
            "condition_state"
        ]
        == "ACTIVE"
    )


def test_unrelated_parameters_and_duplicate_processing(system):
    app, client, _, _ = system
    approve_limit(app)
    approve_limit(app, "vibration_velocity_rms", "mm/s", 3.0)
    ingest_step(app, vibration=5.0)
    app.state.classical.step(app.state.factory, True)
    with app.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 2
        assert db.scalar(select(func.count()).select_from(ProcessingCheckpoint)) == 1
        assert db.scalar(select(func.count()).select_from(Result)) == 3


def test_provider_failure_retry_preserves_messages(system):
    app, client, fake, _ = system
    session = start(client)
    fake.mode = "timeout"
    message = ask(app, client, session)
    assert message["state"] == "error"
    assert message["user_text"] == "What is the current temperature?"
    fake.mode = "valid"
    message = ask(app, client, session)
    assert message["state"] == "completed"
    assert message["attempts"] == 2
    changed = client.post(
        f"/api/v1/troubleshooting/sessions/{session}/messages",
        json={"request_id": "q1", "text": "different"},
    )
    assert changed.status_code == 409


def test_invalid_llm_output_is_controlled(system):
    app, client, fake, _ = system
    fake.mode = "invalid"
    session = start(client)
    message = ask(app, client, session)
    assert message["state"] == "error"
    assert "schema" in message["error"]
    assert len(fake.calls) == 2


def test_current_context_selective_and_stale(system):
    app, client, fake, _ = system
    with app.state.factory.begin() as db:
        ingest(db, telemetry(at=now() - timedelta(hours=1)))
    session = start(client)
    message = ask(app, client, session)
    context = message["response"]["machine_context"]
    assert context["telemetry_stale"]
    assert context["latest_reading"]["readings"][0]["value_normalized"] == 80.0
    assert "recent_history" not in context
    assert "approved_limits" not in context
    assert "incidents" not in context
    assert message["response"]["response_type"] == "INSUFFICIENT_EVIDENCE"


def test_maintenance_is_unverified_and_no_auto_resolution(system):
    app, client, _, _ = system
    approve_limit(app)
    ingest_step(app)
    with app.state.factory() as db:
        session = db.scalar(select(Session))
        sid, incident = session.id, session.incident_id
    response = client.post(
        f"/api/v1/troubleshooting/sessions/{sid}/feedback",
        json={"kind": "maintenance", "text": "Replaced bearing successfully"},
    )
    assert response.status_code == 201
    message = ask(app, client, sid, "Did the intervention work?")
    report = message["response"]["machine_context"]["operator_reports"][0]
    assert report["verified"] is False
    with app.state.factory() as db:
        assert db.get(Alert, incident).status == "active"


def test_pdf_versions_applicability_and_citations(system, pdf):
    app, client, fake, settings = system
    assert upload(client, pdf).status_code == 201
    assert upload(client, pdf).json()["duplicate"]
    assert upload(client, pdf, "v2").status_code == 201
    sid = start(client, document_id="manual", document_version="v2")
    with app.state.factory() as db:
        session = db.get(Session, sid)
        passages, error = retrieve(
            db, fake, settings, session, "Valve-X19 pressure regulator"
        )
        assert not error
        assert all(p["version"] == "v2" and p["page"] == 1 for p in passages)
        assert "10 bar" in passages[0]["text"]
        # A different machine cannot retrieve a manual simply by guessing its identity.
        from types import SimpleNamespace

        other = SimpleNamespace(
            asset_id="not-the-machine", document_id="manual", document_version="v2"
        )
        passages, error = retrieve(db, fake, settings, other, "Valve-X19")
        assert not passages and error
    assert (
        client.post(
            "/api/v1/troubleshooting/sessions",
            json={
                "machine_id": "motor_001",
                "document_id": "manual",
                "document_version": "absent",
            },
        ).status_code
        == 404
    )


def test_no_manual_is_insufficient_evidence(system):
    app, client, _, _ = system
    session = start(client)
    message = ask(app, client, session, "What does the manual say to inspect?")
    assert message["response"]["response_type"] == "INSUFFICIENT_EVIDENCE"
    assert message["response"]["instructions"] == []


@pytest.mark.parametrize("bad", ["citation", "quote", "number", "unsafe"])
def test_response_grounding_rejects_inventions(bad):
    passage = {
        "chunk_id": "chunk",
        "document_id": "manual",
        "version": "v1",
        "page": 1,
        "text": "Inspect the pressure regulator using the manufacturer procedure.",
    }
    source = {k: passage[k] for k in ["chunk_id", "document_id", "version", "page"]}
    answer = {
        "response_type": "TROUBLESHOOTING",
        "condition_summary": "Investigation is needed.",
        "sources": [source],
        "instructions": [
            {
                "title": "Inspection",
                "description": passage["text"],
                "source_quote": passage["text"],
                "source": source,
            }
        ],
    }
    if bad == "citation":
        answer["sources"][0]["page"] = 99
    if bad == "quote":
        answer["instructions"][0]["description"] = "Invented action."
    if bad == "number":
        answer["condition_summary"] = "The limit is 999 bar."
    if bad == "unsafe":
        passage["text"] = "Disable the safety interlock."
        answer["instructions"][0].update(
            description=passage["text"], source_quote=passage["text"]
        )
    with pytest.raises(InvalidAnswer):
        validate_answer(
            json.dumps(answer),
            [passage],
            {"references": [], "limitations": [], "selected_context": ["manual"]},
        )


def test_manual_upload_failure_and_invalid_pdf(system):
    app, client, fake, _ = system
    response = upload(client, b"not a PDF")
    assert response.status_code == 422
    assert client.post("/api/v1/documents", headers=READ).status_code == 401


def test_incident_acknowledgment_separate_from_condition(system):
    app, client, _, _ = system
    approve_limit(app)
    ingest_step(app)
    with app.state.factory() as db:
        incident = db.scalar(select(Alert))
        iid = incident.id
    response = client.post(
        f"/api/v1/alerts/{iid}/acknowledge", json={"reason": "Review started"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["acknowledged_at"]
    assert response.json()["metadata"]["condition_state"] == "ACTIVE"
    assert (
        client.post(
            f"/api/v1/incidents/{iid}/close", json={"reason": "premature"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/alerts/{iid}/resolve", json={"reason": "completed a step"}
        ).status_code
        == 409
    )


def test_incident_api_bounds_and_auth(system):
    app, client, _, _ = system
    assert (
        client.get("/api/v1/assets/motor_001/incidents", headers=READ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/assets/motor_001/incidents?limit=1001", headers=READ
        ).status_code
        == 422
    )
    assert client.get("/api/v1/incidents/missing", headers=READ).status_code == 404
    assert (
        client.get("/api/v1/troubleshooting/sessions?machine_id=motor_001").status_code
        == 401
    )


def test_realtime_outbox_and_authentication(system):
    from fastapi.testclient import TestClient

    app, _, _, _ = system
    with TestClient(app) as live:
        with live.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"authorization": "Bearer read"})
            response = live.post(
                "/api/v1/troubleshooting/sessions",
                headers={"Authorization": "Bearer operator"},
                json={"machine_id": "motor_001"},
            )
            assert response.status_code == 201
            event = ws.receive_json()
            assert event["event_type"] == "troubleshooting.started"
            assert event["payload"]["session_id"] == response.json()["id"]
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with live.websocket_connect("/api/v1/ws") as ws:
                ws.send_json({"authorization": "Bearer wrong"})
                ws.receive_json()


def test_embedding_failure_is_not_synthetic_success(system, pdf, monkeypatch):
    app, client, fake, _ = system

    def fail(texts):
        raise ProviderError("Embedding service unavailable")

    monkeypatch.setattr(fake, "embed", fail)
    response = upload(client, pdf)
    assert response.status_code == 503
    with app.state.factory() as db:
        from AI.models import Manual

        assert db.scalar(select(func.count()).select_from(Manual)) == 0


def test_scanned_pdf_requires_explicit_ocr(system):
    import pymupdf

    app, client, _, _ = system
    document = pymupdf.open()
    document.new_page()
    pdf = document.tobytes()
    document.close()
    response = upload(client, pdf)
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]


def test_manual_model_filter_and_conflicting_versions(system, pdf):
    app, client, fake, settings = system
    assert upload(client, pdf).status_code == 201
    with app.state.factory.begin() as db:
        from backend.app.db import Asset

        asset = db.get(Asset, "motor_001")
        asset.metadata_json = {
            **asset.metadata_json,
            "machine_model": "different model",
        }
    sid = start(client, document_id="manual", document_version="v1")
    message = ask(app, client, sid, "What does the manual say to inspect?")
    assert message["response"]["response_type"] == "INSUFFICIENT_EVIDENCE"
    assert message["response"]["sources"] == []


def test_expired_processing_lease_is_recovered(system):
    app, client, fake, settings = system
    sid = start(client)
    with app.state.factory.begin() as db:
        db.add(
            Message(
                session_id=sid,
                request_id="crash",
                user_text="What is the current pressure?",
                state="processing",
                processing_at=now() - timedelta(minutes=20),
            )
        )
    assert app.state.troubleshooting.process_one(app.state.factory)
    with app.state.factory() as db:
        assert db.scalar(select(Message)).state == "completed"


def test_closed_incident_starts_new_incident_on_recurrence(system):
    app, client, _, _ = system
    approve_limit(app)
    at = now()
    ingest_step(app, at=at)
    with app.state.factory() as db:
        iid = db.scalar(select(Alert.id))
    for i in range(3):
        ingest_step(
            app, "normal-close-" + str(i), 50.0, at=at + timedelta(seconds=3 + i * 3)
        )
    assert (
        client.post(
            f"/api/v1/incidents/{iid}/close", json={"reason": "Recovery reviewed"}
        ).status_code
        == 200
    )
    ingest_step(app, "after-close", 80.0, at=at + timedelta(seconds=12))
    with app.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(Alert)) == 2


def test_late_normal_observation_does_not_recover_newer_incident(system):
    app, client, _, _ = system
    approve_limit(app)
    at = now()
    ingest_step(app, at=at)
    ingest_step(app, "newer", 82.0, at=at + timedelta(seconds=12))
    ingest_step(app, "late-normal", 50.0, at=at + timedelta(seconds=3))
    with app.state.factory() as db:
        incident = db.scalar(select(Alert))
        assert incident.metadata_json["condition_state"] == "ACTIVE"
        assert incident.metadata_json["normal_count"] == 0


def test_upgrade_preserves_legacy_incidents(system):
    from pathlib import Path
    from sqlalchemy import text
    from backend.app.manage import migrate

    app, _, _, _ = system
    engine = app.state.engine
    if engine.dialect.name != "postgresql":
        pytest.skip("Requires a disposable PostgreSQL database")
    # Reconstruct the actual pre-extension schema and records, then apply forward migrations.
    from sqlalchemy import MetaData

    metadata = MetaData()
    metadata.reflect(bind=engine)
    metadata.drop_all(engine)
    root = Path(__file__).resolve().parents[2]
    with engine.begin() as conn:
        for name in ["001_initial.sql", "002_policy_versions.sql"]:
            conn.exec_driver_sql((root / "backend/migrations" / name).read_text())
        conn.exec_driver_sql(
            "CREATE TABLE schema_migrations(version text PRIMARY KEY,applied_at timestamptz DEFAULT now())"
        )
        conn.exec_driver_sql(
            "INSERT INTO schema_migrations(version) VALUES ('001_initial.sql'),('002_policy_versions.sql')"
        )
        conn.exec_driver_sql(
            """INSERT INTO assets(asset_id,name,metadata,created_at) VALUES ('legacy','Legacy asset','{}',now())"""
        )
        conn.exec_driver_sql("""INSERT INTO anomaly_decisions(id,asset_id,window_id,decided_at,final_status,policy_version,evidence,decision_reason,alert_processed)
            VALUES ('legacy-decision','legacy','legacy-window',now(),'anomaly','legacy','[]','{}',true)""")
        conn.exec_driver_sql("""INSERT INTO alerts(id,asset_id,decision_id,created_at,status,metadata)
            VALUES ('legacy-alert','legacy','legacy-decision',now(),'active','{}')""")
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT incident_key FROM alerts WHERE id='legacy-alert'"))
            == "__machine__"
        )
        assert conn.scalar(text("SELECT count(*) FROM schema_migrations")) == 4
        assert (
            conn.scalar(text("SELECT status FROM alerts WHERE id='legacy-alert'"))
            == "active"
        )


def test_old_anomaly_cannot_close_current_incident(system):
    app, client, _, _ = system
    approve_limit(app)
    at = now()
    ingest_step(app, at=at)
    ingest_step(app, "historical", 82.0, at=at - timedelta(minutes=10))
    ingest_step(app, "current-again", 83.0, at=at + timedelta(seconds=3))
    with app.state.factory() as db:
        active = db.scalars(select(Alert).where(Alert.status == "active")).all()
        assert len(active) == 1
        assert active[0].metadata_json["observation_count"] == 2
        assert db.scalar(select(func.count()).select_from(AnomalyEvent)) == 3


def test_mqtt_disconnection_marks_even_recent_reading_stale(system):
    app, client, _, settings = system
    with app.state.factory.begin() as db:
        ingest(db, telemetry())
    settings.mqtt_enabled = True
    app.state.troubleshooting.connection_check = lambda: False
    sid = start(client)
    message = ask(app, client, sid)
    assert message["response"]["machine_context"]["mqtt_connected"] is False
    assert message["response"]["machine_context"]["telemetry_stale"] is True
    assert message["response"]["response_type"] == "INSUFFICIENT_EVIDENCE"


def test_authoritative_summary_overrides_model_paraphrase(system, monkeypatch):
    app, client, fake, _ = system
    with app.state.factory.begin() as db:
        ingest(db, telemetry(temperature=81.5))
    previous = fake.chat

    def contradictory(messages, schema):
        response = json.loads(previous(messages, schema))
        response["condition_summary"] = "No sensor data exists."
        return json.dumps(response)

    monkeypatch.setattr(fake, "chat", contradictory)
    sid = start(client)
    message = ask(app, client, sid)
    assert "81.5" in message["response"]["condition_summary"]
    assert "motor_temperature" in message["response"]["condition_summary"]
    assert "No sensor data exists" not in message["response"]["condition_summary"]


def test_sparse_normal_observations_do_not_satisfy_recovery(system):
    app, client, _, _ = system
    approve_limit(app)
    at = now()
    ingest_step(app, at=at)
    for index in range(1, 4):
        ingest_step(
            app, "sparse-" + str(index), 50.0, at=at + timedelta(seconds=index * 10)
        )
    with app.state.factory() as db:
        incident = db.scalar(select(Alert))
        assert incident.metadata_json["condition_state"] != "RESOLVED"
        assert incident.metadata_json["normal_count"] == 1


def test_exact_component_question_and_followup_retrieve_manual(system, pdf):
    app, client, fake, _ = system
    assert upload(client, pdf).status_code == 201
    sid = start(client, document_id="manual", document_version="v1")
    first = ask(app, client, sid, "Valve-X19?", request="component")
    assert first["state"] == "completed"
    assert first["response"]["sources"]
    second = ask(app, client, sid, "What about that component?", request="followup")
    assert second["state"] == "completed"
    data = json.loads(fake.calls[-1][1]["content"])
    assert data["conversation_history"][0]["user"] == "Valve-X19?"
    assert second["response"]["sources"][0]["document_id"] == "manual"

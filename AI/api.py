import asyncio
import hmac
from fastapi.responses import JSONResponse
from .provider import ProviderError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select
from backend.app.db import Asset, Alert, AlertEvent
from backend.app.main import serialize
from backend.app.services import DomainError, lock_asset
from .models import Session, Message, Evidence, Step, Feedback, Manual, emit
from .schemas import StartSession, Ask, Report
from .rag import ingest_manual


def install(app, settings, factory, reader, operator, service, hub):
    router = APIRouter(prefix="/api/v1")

    def db_session():
        with factory.begin() as db:
            yield db

    def session_or_404(db, session_id, lock=False):
        stmt = select(Session).where(Session.id == session_id)
        if lock:
            stmt = stmt.with_for_update()
        session = db.scalar(stmt)
        if not session:
            raise DomainError("Session not found", 404)
        return session

    def collection(db, stmt, limit, offset):
        rows = db.scalars(stmt.limit(limit + 1).offset(offset)).all()
        return {
            "items": [serialize(row) for row in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if len(rows) > limit else None,
        }

    @router.post(
        "/troubleshooting/sessions", dependencies=[Depends(operator)], status_code=201
    )
    def start(payload: StartSession, db=Depends(db_session)):
        lock_asset(db, payload.machine_id)
        if payload.incident_id:
            incident = db.get(Alert, payload.incident_id)
            if not incident or incident.asset_id != payload.machine_id:
                raise DomainError("Incident does not belong to selected machine", 404)
            existing = db.scalar(
                select(Session).where(Session.incident_id == incident.id)
            )
            if existing:
                return serialize(existing)
        if payload.document_id:
            manual = db.scalar(
                select(Manual).where(
                    Manual.asset_id == payload.machine_id,
                    Manual.document_id == payload.document_id,
                    Manual.version == payload.document_version,
                )
            )
            if not manual:
                raise DomainError("Manual version is not indexed for this machine", 404)
        session = Session(
            asset_id=payload.machine_id,
            incident_id=payload.incident_id,
            document_id=payload.document_id,
            document_version=payload.document_version,
        )
        db.add(session)
        db.flush()
        emit(
            db,
            session.asset_id,
            "troubleshooting.started",
            {"session_id": session.id, "incident_id": session.incident_id},
        )
        db.commit()
        return serialize(session)

    @router.patch(
        "/troubleshooting/sessions/{session_id}/manual",
        dependencies=[Depends(operator)],
    )
    def select_manual(session_id: str, payload: StartSession, db=Depends(db_session)):
        session = session_or_404(db, session_id, True)
        if (
            session.asset_id != payload.machine_id
            or session.incident_id != payload.incident_id
        ):
            raise DomainError("Machine/incident identity must remain unchanged", 409)
        if db.scalar(
            select(Message.id).where(
                Message.session_id == session_id,
                Message.state.in_(["pending", "processing"]),
            )
        ):
            raise DomainError(
                "Wait for pending messages before changing the manual", 409
            )
        if payload.document_id and not db.scalar(
            select(Manual.id).where(
                Manual.asset_id == session.asset_id,
                Manual.document_id == payload.document_id,
                Manual.version == payload.document_version,
            )
        ):
            raise DomainError("Manual version is not indexed for this machine", 404)
        session.document_id, session.document_version = (
            payload.document_id,
            payload.document_version,
        )
        db.commit()
        return serialize(session)

    @router.get("/troubleshooting/sessions", dependencies=[Depends(reader)])
    def sessions(
        machine_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        return collection(
            db,
            select(Session)
            .where(Session.asset_id == machine_id)
            .order_by(Session.created_at, Session.id),
            limit,
            offset,
        )

    @router.get(
        "/troubleshooting/sessions/{session_id}", dependencies=[Depends(reader)]
    )
    def detail(
        session_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        session = session_or_404(db, session_id)
        data = serialize(session)
        data["messages"] = collection(
            db,
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at, Message.id),
            limit,
            offset,
        )
        data["steps"] = collection(
            db,
            select(Step).where(Step.session_id == session_id).order_by(Step.id),
            limit,
            offset,
        )
        data["feedback"] = collection(
            db,
            select(Feedback)
            .where(Feedback.session_id == session_id)
            .order_by(Feedback.created_at, Feedback.id),
            limit,
            offset,
        )
        if session.incident_id:
            data["incident"] = serialize(db.get(Alert, session.incident_id))
        return data

    @router.post(
        "/troubleshooting/sessions/{session_id}/messages",
        dependencies=[Depends(operator)],
        status_code=202,
    )
    def ask(session_id: str, payload: Ask, db=Depends(db_session)):
        session = session_or_404(db, session_id, True)
        existing = db.scalar(
            select(Message).where(
                Message.session_id == session_id,
                Message.request_id == payload.request_id,
            )
        )
        if existing:
            if existing.user_text != payload.text:
                raise DomainError("request_id reused with different text", 409)
            if existing.state == "error":
                existing.state, existing.error, session.state = (
                    "pending",
                    None,
                    "pending",
                )
            db.commit()
            return serialize(existing)
        if db.scalar(
            select(Message.id).where(
                Message.session_id == session_id,
                Message.state.in_(["pending", "processing"]),
            )
        ):
            raise DomainError("This session already has a pending response", 409)
        message = Message(
            session_id=session_id, request_id=payload.request_id, user_text=payload.text
        )
        db.add(message)
        session.state = "pending"
        db.flush()
        db.commit()
        return serialize(message)

    @router.get(
        "/troubleshooting/sessions/{session_id}/evidence",
        dependencies=[Depends(reader)],
    )
    def evidence(
        session_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        session_or_404(db, session_id)
        return collection(
            db,
            select(Evidence)
            .join(Message, Evidence.message_id == Message.id)
            .where(Message.session_id == session_id)
            .order_by(Evidence.id),
            limit,
            offset,
        )

    @router.post(
        "/troubleshooting/sessions/{session_id}/feedback",
        dependencies=[Depends(operator)],
        status_code=201,
    )
    def feedback(session_id: str, payload: Report, db=Depends(db_session)):
        session = session_or_404(db, session_id, True)
        if payload.kind.startswith("step_") and not payload.step_id:
            raise DomainError("Step feedback requires step_id")
        if payload.step_id:
            step = db.get(Step, payload.step_id)
            if not step or step.session_id != session_id:
                raise DomainError("Step does not belong to session", 404)
            if payload.kind in ["step_completed", "step_not_completed"]:
                step.state = payload.kind
        report = Feedback(
            session_id=session_id,
            incident_id=session.incident_id,
            step_id=payload.step_id,
            kind=payload.kind,
            text=payload.text,
        )
        db.add(report)
        db.flush()
        emit(
            db,
            session.asset_id,
            "troubleshooting.step_updated",
            {
                "session_id": session_id,
                "step_id": payload.step_id,
                "feedback_id": report.id,
                "provenance": "operator_reported",
            },
        )
        db.commit()
        return serialize(report)

    @router.get("/documents", dependencies=[Depends(reader)])
    def documents(
        machine_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        return collection(
            db,
            select(Manual)
            .where(Manual.asset_id == machine_id)
            .order_by(Manual.document_id, Manual.version),
            limit,
            offset,
        )

    @router.post("/documents", dependencies=[Depends(operator)], status_code=201)
    def upload(
        document_id: str = Form(..., min_length=1, max_length=200, pattern=r"^\S+$"),
        version: str = Form(..., min_length=1, max_length=200, pattern=r"^\S+$"),
        machine_id: str = Form(..., min_length=1, max_length=200, pattern=r"^\S+$"),
        manufacturer: str = Form(..., min_length=1, max_length=200),
        machine_model: str = Form(..., min_length=1, max_length=200),
        file: UploadFile = File(...),
        db=Depends(db_session),
    ):
        content = file.file.read(15 * 1024 * 1024 + 1)
        manual, duplicate = ingest_manual(
            db,
            service.provider,
            settings,
            content,
            document_id,
            version,
            machine_id,
            manufacturer,
            machine_model,
        )
        db.commit()
        return {"document": serialize(manual), "duplicate": duplicate}

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    app.include_router(router)

    @app.websocket("/api/v1/ws")
    async def websocket(socket: WebSocket):
        await socket.accept()
        try:
            auth = await asyncio.wait_for(socket.receive_json(), timeout=5)
            supplied = auth.get("authorization", "")
            if not settings.api_token or not hmac.compare_digest(
                supplied, "Bearer " + settings.api_token
            ):
                await socket.close(code=1008)
                return
        except (
            ValueError,
            TypeError,
            AttributeError,
            asyncio.TimeoutError,
            WebSocketDisconnect,
        ):
            await socket.close(code=1008)
            return
        queue = asyncio.Queue(maxsize=64)
        hub.clients.add(queue)

        async def send():
            while True:
                item = await queue.get()
                await socket.send_json(item)
                if item.get("event_type") == "resync_required":
                    await socket.close(code=1013)
                    return

        async def receive():
            while True:
                await socket.receive_text()

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            hub.clients.discard(queue)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def install_incidents(app, factory, reader, operator):
    from ML.persistence import AnomalyEvent
    from backend.app.schemas import Action

    router = APIRouter(prefix="/api/v1")

    def db_session():
        with factory.begin() as db:
            yield db

    @router.get("/assets/{asset_id}/approved-limits", dependencies=[Depends(reader)])
    def approved_limits(asset_id: str, db=Depends(db_session)):
        if not db.get(Asset, asset_id):
            raise DomainError("Unknown machine", 404)
        limits = [
            limit.model_dump(mode="json")
            for limit in app.state.classical.limits
            if limit.machine_id == asset_id and limit.status.value == "approved"
        ]
        return {
            "machine_id": asset_id,
            "limits": limits,
            "available": bool(limits),
            "authority": "reviewed_configuration",
            "applicability": "Review the recorded operating mode, units and time basis; this response does not assert all limits apply now",
        }

    @router.get("/assets/{asset_id}/incidents", dependencies=[Depends(reader)])
    def incidents(
        asset_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        if not db.get(Asset, asset_id):
            raise DomainError("Unknown machine", 404)
        rows = db.scalars(
            select(Alert)
            .where(Alert.asset_id == asset_id)
            .order_by(Alert.created_at, Alert.id)
            .limit(limit + 1)
            .offset(offset)
        ).all()
        return {
            "items": [serialize(row) for row in rows[:limit]],
            "next_offset": offset + limit if len(rows) > limit else None,
            "limit": limit,
            "offset": offset,
        }

    @router.get("/incidents/{incident_id}", dependencies=[Depends(reader)])
    def incident(
        incident_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        db=Depends(db_session),
    ):
        data = serialize(db.get(Alert, incident_id))
        events = db.scalars(
            select(AnomalyEvent)
            .where(AnomalyEvent.incident_id == incident_id)
            .order_by(AnomalyEvent.observed_at, AnomalyEvent.id)
            .limit(limit + 1)
            .offset(offset)
        ).all()
        data["observations"] = {
            "items": [serialize(row) for row in events[:limit]],
            "next_offset": offset + limit if len(events) > limit else None,
            "limit": limit,
            "offset": offset,
        }
        return data

    @router.post("/incidents/{incident_id}/close", dependencies=[Depends(operator)])
    def close(incident_id: str, payload: Action, db=Depends(db_session)):
        alert = db.get(Alert, incident_id)
        if not alert:
            raise DomainError("Incident not found", 404)
        lock_asset(db, alert.asset_id)
        db.refresh(alert)
        if alert.metadata_json.get("condition_state") != "RESOLVED":
            raise DomainError("Only recovered/resolved incidents can be closed", 409)
        alert.metadata_json = {**alert.metadata_json, "condition_state": "CLOSED"}
        db.add(
            AlertEvent(
                alert_id=alert.id,
                event_type="closed",
                details={"actor": "operator", "reason": payload.reason},
            )
        )
        emit(
            db,
            alert.asset_id,
            "incident.updated",
            {"incident_id": alert.id, "state": "CLOSED"},
        )
        db.commit()
        return serialize(alert)

    app.include_router(router)

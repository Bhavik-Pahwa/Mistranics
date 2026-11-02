import hmac
import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from .config import Settings
from .db import Asset, Reading, Result, Decision, Alert, AlertEvent, connect, now
from .schemas import DetectorResult, Action, Policy, Time
from .services import (
    DomainError,
    load_registry,
    seed,
    accept_result,
    process_pending,
    transition,
    register_policy,
)
from .mqtt import Subscriber

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger(__name__)


def serialize(row):
    if row is None:
        raise HTTPException(404, "Resource not found")
    result = {col.key: getattr(row, col.key) for col in row.__mapper__.column_attrs}
    if "metadata_json" in result:
        result["metadata"] = result.pop("metadata_json")
    if isinstance(row, Reading):
        result.pop("original", None)
        result["machine_id"] = result.pop("asset_id")
    result = {
        k: (
            v.replace(tzinfo=timezone.utc)
            if isinstance(v, datetime) and v.tzinfo is None
            else v
        )
        for k, v in result.items()
    }
    return jsonable_encoder(result)


def create_app(settings=None):
    settings = settings or Settings()
    engine, factory = connect(settings.database_url)
    registry = load_registry(settings.registry_file)
    policy = (
        Policy.model_validate_json(Path(settings.policy_file).read_text())
        if settings.policy_file
        else None
    )
    if (settings.ml_enabled or settings.ai_enabled) and __package__ != "backend.app":
        raise RuntimeError(
            "AI/ML extensions require the repository-root entry point: backend.app.main:create_app"
        )
    classical = None
    if settings.ml_enabled or settings.ai_enabled:
        from ML.runtime import Runtime

        classical = Runtime(settings)
    if settings.ml_enabled and policy and policy.alerts_enabled:
        raise RuntimeError(
            "Disable legacy policy alerts when ML_ENABLED uses parameter-level incident management"
        )
    stop = threading.Event()

    def worker():
        while not stop.wait(3 if settings.ml_enabled else settings.retry_seconds):
            if settings.ml_enabled:
                try:
                    classical.step(factory, settings.ai_enabled)
                except Exception:
                    log.exception(
                        "Classical ML integration failed; persisted telemetry remains pending"
                    )
            try:
                process_pending(factory, policy)
            except Exception:
                log.exception("Pending processing failed; will retry")

    def ai_worker():
        while not stop.wait(0.5):
            try:
                troubleshooting.process_one(factory)
            except Exception:
                log.exception("AI processing failed; persisted messages will retry")

    async def publish_events(loop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(hub.deliver, factory, loop)
            except Exception:
                log.exception("Event publication failed; outbox remains pending")
            await asyncio.sleep(0.5)

    @asynccontextmanager
    async def lifespan(app):
        if not settings.internal_token or not settings.operator_token:
            raise RuntimeError("INTERNAL_TOKEN and OPERATOR_TOKEN must be configured")
        with factory.begin() as session:
            session.execute(text("SELECT 1"))
            seed(session, registry)
            register_policy(session, policy)
            if settings.ml_enabled:
                register_policy(
                    session,
                    classical.policy.model_copy(
                        update={"version": "classical:" + classical.policy.version}
                    ),
                )
        thread = threading.Thread(target=worker, daemon=True)
        subscriber = Subscriber(settings, factory) if settings.mqtt_enabled else None
        app.state.mqtt_subscriber = subscriber
        thread.start()
        ai_thread = None
        publisher_task = None
        if settings.ai_enabled:
            ai_thread = threading.Thread(target=ai_worker, daemon=True)
            publisher_task = asyncio.create_task(
                publish_events(asyncio.get_running_loop())
            )
            ai_thread.start()
        try:
            if subscriber:
                subscriber.start()
            log.info(
                "Backend started decision_policy=%s",
                policy.version if policy else "unavailable",
            )
            yield
        finally:
            stop.set()
            if publisher_task:
                publisher_task.cancel()
                await asyncio.gather(publisher_task, return_exceptions=True)
            if subscriber:
                subscriber.stop()
            thread.join(timeout=5)
            if ai_thread:
                ai_thread.join(timeout=5)
            engine.dispose()
            log.info("Backend stopped")

    app = FastAPI(title="Mistranics Backend", version="1.0.0", lifespan=lifespan)
    app.state.factory, app.state.engine, app.state.policy = factory, engine, policy

    def authorization(expected, value):
        if (
            not expected
            or not value
            or not hmac.compare_digest(value, "Bearer " + expected)
        ):
            raise HTTPException(
                401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"}
            )

    def reader(authorization_header: str | None = Header(None, alias="Authorization")):
        if settings.api_token:
            authorization(settings.api_token, authorization_header)

    def internal(
        authorization_header: str | None = Header(None, alias="Authorization"),
    ):
        authorization(settings.internal_token, authorization_header)

    def operator(
        authorization_header: str | None = Header(None, alias="Authorization"),
    ):
        authorization(settings.operator_token, authorization_header)

    def db():
        with factory.begin() as session:
            yield session

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        log.warning("API validation rejected path=%s", request.url.path)
        return JSONResponse(
            {
                "detail": [
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ]
            },
            status_code=422,
        )

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        log.warning("Request rejected path=%s status=%s", request.url.path, exc.status)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request, exc):
        log.error(
            "Database operation failed path=%s type=%s",
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            {"detail": "Database unavailable or operation failed"}, status_code=503
        )

    @app.exception_handler(Exception)
    async def unknown_error(request, exc):
        log.error(
            "Internal error path=%s type=%s", request.url.path, type(exc).__name__
        )
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    @app.get("/health")
    def health(session=Depends(db)):
        session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "decision_policy": policy.version if policy else None,
            "mqtt_enabled": settings.mqtt_enabled,
        }

    prefix = "/api/v1"
    read_deps = [Depends(reader)]

    def asset_exists(session, asset_id):
        if not session.get(Asset, asset_id):
            raise HTTPException(404, "Asset not found")

    def bounds(start, end):
        end = end or now()
        start = start or end - timedelta(seconds=settings.context_seconds)
        if start >= end or end - start > timedelta(days=settings.max_query_days):
            raise HTTPException(422, "Invalid range or exceeds maximum query days")
        return start, end

    def page(session, stmt, limit, offset):
        rows = session.scalars(stmt.offset(offset).limit(limit + 1)).all()
        return {
            "items": [serialize(r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if len(rows) > limit else None,
        }

    @app.get(prefix + "/assets", dependencies=read_deps)
    def assets(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        return page(session, select(Asset).order_by(Asset.asset_id), limit, offset)

    @app.get(prefix + "/assets/{asset_id}", dependencies=read_deps)
    def asset(asset_id: str, session=Depends(db)):
        return serialize(session.get(Asset, asset_id))

    @app.get(prefix + "/assets/{asset_id}/readings/latest", dependencies=read_deps)
    def latest(asset_id: str, session=Depends(db)):
        asset_exists(session, asset_id)
        return serialize(
            session.scalar(
                select(Reading)
                .where(Reading.asset_id == asset_id)
                .order_by(Reading.measured_at.desc(), Reading.window_id.desc())
                .limit(1)
            )
        )

    @app.get(prefix + "/assets/{asset_id}/readings", dependencies=read_deps)
    def readings(
        asset_id: str,
        start: Time | None = None,
        end: Time | None = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        asset_exists(session, asset_id)
        start, end = bounds(start, end)
        return page(
            session,
            select(Reading)
            .where(
                Reading.asset_id == asset_id,
                Reading.measured_at >= start,
                Reading.measured_at <= end,
            )
            .order_by(Reading.measured_at, Reading.window_id),
            limit,
            offset,
        )

    @app.post(prefix + "/internal/detector-results", dependencies=[Depends(internal)])
    def submit(payload: DetectorResult, session=Depends(db)):
        result, duplicate = accept_result(session, payload.model_dump(mode="json"))
        # Commit acceptance before processing. Persistent worker resumes on failure.
        session.commit()
        return {"result": serialize(result), "duplicate": duplicate}

    @app.get(prefix + "/assets/{asset_id}/detector-results", dependencies=read_deps)
    def results(
        asset_id: str,
        start: Time | None = None,
        end: Time | None = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        asset_exists(session, asset_id)
        start, end = bounds(start, end)
        return page(
            session,
            select(Result)
            .where(
                Result.asset_id == asset_id,
                Result.evaluated_at >= start,
                Result.evaluated_at <= end,
            )
            .order_by(Result.evaluated_at, Result.id),
            limit,
            offset,
        )

    @app.get(prefix + "/detector-results/{result_id}", dependencies=read_deps)
    def result(result_id: str, session=Depends(db)):
        return serialize(session.get(Result, result_id))

    @app.get(prefix + "/assets/{asset_id}/anomalies", dependencies=read_deps)
    def decisions(
        asset_id: str,
        start: Time | None = None,
        end: Time | None = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        asset_exists(session, asset_id)
        start, end = bounds(start, end)
        return page(
            session,
            select(Decision)
            .where(
                Decision.asset_id == asset_id,
                Decision.decided_at >= start,
                Decision.decided_at <= end,
            )
            .order_by(Decision.decided_at, Decision.id),
            limit,
            offset,
        )

    @app.get(prefix + "/anomalies/{decision_id}", dependencies=read_deps)
    def decision(decision_id: str, session=Depends(db)):
        return serialize(session.get(Decision, decision_id))

    @app.get(prefix + "/alerts", dependencies=read_deps)
    def alerts(
        asset_id: str | None = None,
        status: str | None = Query(None, pattern="^(active|acknowledged|resolved)$"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        stmt = select(Alert)
        if asset_id:
            stmt = stmt.where(Alert.asset_id == asset_id)
        if status:
            stmt = stmt.where(Alert.status == status)
        return page(session, stmt.order_by(Alert.created_at, Alert.id), limit, offset)

    @app.get(prefix + "/alerts/{alert_id}", dependencies=read_deps)
    def alert(
        alert_id: str,
        event_limit: int = Query(100, ge=1, le=1000),
        event_offset: int = Query(0, ge=0, le=1000000),
        session=Depends(db),
    ):
        item = serialize(session.get(Alert, alert_id))
        item["events"] = page(
            session,
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(AlertEvent.occurred_at, AlertEvent.id),
            event_limit,
            event_offset,
        )
        return item

    @app.post(
        prefix + "/alerts/{alert_id}/acknowledge", dependencies=[Depends(operator)]
    )
    def acknowledge(alert_id: str, payload: Action, session=Depends(db)):
        row = transition(session, alert_id, "acknowledge", payload.reason, policy)
        session.commit()
        return serialize(row)

    @app.post(prefix + "/alerts/{alert_id}/resolve", dependencies=[Depends(operator)])
    def resolve(alert_id: str, payload: Action, session=Depends(db)):
        row = transition(session, alert_id, "resolve", payload.reason, policy)
        session.commit()
        return serialize(row)

    @app.get(prefix + "/assets/{asset_id}/diagnostic-context", dependencies=read_deps)
    def context(asset_id: str, session=Depends(db)):
        asset_exists(session, asset_id)
        start = now() - timedelta(seconds=settings.context_seconds)
        return {
            "asset": serialize(session.get(Asset, asset_id)),
            "from": start,
            "as_of": now(),
            "readings": page(
                session,
                select(Reading)
                .where(Reading.asset_id == asset_id, Reading.measured_at >= start)
                .order_by(Reading.measured_at, Reading.window_id),
                100,
                0,
            ),
            "detector_results": page(
                session,
                select(Result)
                .where(Result.asset_id == asset_id, Result.received_at >= start)
                .order_by(Result.received_at, Result.id),
                100,
                0,
            ),
            "decisions": page(
                session,
                select(Decision)
                .where(Decision.asset_id == asset_id, Decision.decided_at >= start)
                .order_by(Decision.decided_at, Decision.id),
                100,
                0,
            ),
            "active_alerts": page(
                session,
                select(Alert)
                .where(
                    Alert.asset_id == asset_id,
                    Alert.status.in_(["active", "acknowledged"]),
                )
                .order_by(Alert.created_at, Alert.id),
                100,
                0,
            ),
        }

    if settings.ml_enabled or settings.ai_enabled:
        from AI.api import install_incidents

        install_incidents(app, factory, reader, operator)
        app.state.classical = classical
    if settings.ai_enabled:
        from AI.api import install
        from AI.provider import OllamaProvider
        from AI.service import Troubleshooting
        from AI.realtime import Hub

        hub = Hub()
        troubleshooting = Troubleshooting(
            settings, OllamaProvider(settings), classical.limits
        )
        troubleshooting.connection_check = lambda: bool(
            getattr(app.state, "mqtt_subscriber", None)
            and app.state.mqtt_subscriber.client.is_connected()
        )
        install(app, settings, factory, reader, operator, troubleshooting, hub)
        app.state.troubleshooting, app.state.hub = troubleshooting, hub
    return app

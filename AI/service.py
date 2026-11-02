import logging
from datetime import timedelta
from sqlalchemy import select
from backend.app.db import now
from .models import Session, Message, Evidence, Step, emit
from .context import assemble, plan, finalize_condition
from .rag import retrieve
from .reasoning import reason, InvalidAnswer
from .provider import ProviderError

log = logging.getLogger(__name__)


class Troubleshooting:
    def __init__(self, settings, provider, limits):
        self.settings, self.provider, self.limits = settings, provider, limits
        self.connection_check = None

    def process_one(self, factory):
        # Claim and persist the operator message before any provider call.
        with factory.begin() as db:
            candidate = db.scalar(
                select(Message)
                .where(
                    (Message.state == "pending")
                    | (
                        (Message.state == "processing")
                        & (
                            Message.processing_at
                            < now()
                            - timedelta(
                                seconds=self.settings.ai_provider_timeout * 3 + 30
                            )
                        )
                    )
                )
                .order_by(Message.created_at, Message.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not candidate:
                return False
            message_id, session_id, question = (
                candidate.id,
                candidate.session_id,
                candidate.user_text,
            )
            candidate.state, candidate.processing_at = "processing", now()
            candidate.attempts += 1
            session = db.get(Session, session_id)
            session.state = "processing"
            emit(
                db,
                session.asset_id,
                "troubleshooting.processing",
                {"session_id": session_id, "message_id": message_id},
            )
        try:
            with factory() as db:
                session = db.get(Session, session_id)
                history_rows = db.scalars(
                    select(Message)
                    .where(
                        Message.session_id == session_id,
                        Message.id != message_id,
                        Message.created_at <= candidate.created_at,
                    )
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(8)
                ).all()
                history = [
                    {
                        "user": row.user_text,
                        "assistant": row.response,
                        "state": row.state,
                    }
                    for row in reversed(history_rows)
                ]
                # Include recent questions to resolve short follow-ups without loading all data.
                query = " ".join(
                    [row.user_text for row in history_rows[:2]] + [question]
                )
                context = assemble(db, session, query, self.settings, self.limits)
                if self.settings.mqtt_enabled and self.connection_check:
                    context["mqtt_connected"] = self.connection_check()
                    if not context["mqtt_connected"]:
                        context["telemetry_stale"] = True
                        context["limitations"].append(
                            "MQTT is disconnected; live telemetry availability is unverified"
                        )
                passages = []
                if "manual" in plan(query):
                    try:
                        passages, limitation = retrieve(
                            db, self.provider, self.settings, session, query[-8000:]
                        )
                    except ProviderError as exc:
                        limitation = str(exc)
                    if limitation:
                        context["limitations"].append(limitation)
            with factory.begin() as db:
                for passage in passages:
                    if not db.scalar(
                        select(Evidence.id).where(
                            Evidence.message_id == message_id,
                            Evidence.chunk_id == passage["chunk_id"],
                        )
                    ):
                        db.add(
                            Evidence(
                                message_id=message_id,
                                chunk_id=passage["chunk_id"],
                                snapshot=passage,
                            )
                        )
            # Do not hold telemetry/database write transactions during network reasoning.
            answer = reason(self.provider, question, history, context, passages)
            answer = finalize_condition(answer, context, self.settings)
            response = answer.model_dump(mode="json") | {
                "session_id": session_id,
                "machine_context": context,
            }
            with factory.begin() as db:
                message = db.get(Message, message_id)
                session = db.get(Session, session_id)
                for instruction in answer.instructions:
                    db.add(
                        Step(
                            session_id=session_id,
                            message_id=message_id,
                            instruction=instruction.model_dump(mode="json"),
                        )
                    )
                message.response, message.state, message.error = (
                    response,
                    "completed",
                    None,
                )
                session.state = "ready"
                emit(
                    db,
                    session.asset_id,
                    "troubleshooting.response",
                    {
                        "session_id": session_id,
                        "message_id": message_id,
                        "state": "completed",
                    },
                )
        except (ProviderError, InvalidAnswer) as exc:
            self.fail(factory, message_id, session_id, str(exc))
        except Exception:
            log.exception("Troubleshooting processing failed message=%s", message_id)
            self.fail(
                factory,
                message_id,
                session_id,
                "Troubleshooting failed; retry is available",
            )
        return True

    def fail(self, factory, message_id, session_id, error):
        log.warning(
            "Troubleshooting unavailable message=%s reason=%s", message_id, error
        )
        with factory.begin() as db:
            message, session = db.get(Message, message_id), db.get(Session, session_id)
            message.state, message.error, session.state = "error", error, "error"
            emit(
                db,
                session.asset_id,
                "troubleshooting.response",
                {
                    "session_id": session_id,
                    "message_id": message_id,
                    "state": "error",
                    "error": error,
                },
            )

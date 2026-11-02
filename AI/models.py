from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db import Base, J, now, uid


class Manual(Base):
    __tablename__ = "ai_documents"
    __table_args__ = (UniqueConstraint("document_id", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    document_id: Mapped[str]
    version: Mapped[str]
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    manufacturer: Mapped[str]
    machine_model: Mapped[str]
    sha256: Mapped[str]
    embedding_model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chunk(Base):
    __tablename__ = "ai_document_chunks"
    __table_args__ = (Index("ix_chunks_manual", "manual_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    manual_id: Mapped[str] = mapped_column(ForeignKey("ai_documents.id"))
    page: Mapped[int]
    section: Mapped[str]
    text: Mapped[str]
    embedding: Mapped[list] = mapped_column(J)


class Session(Base):
    __tablename__ = "troubleshooting_sessions"
    __table_args__ = (Index("ix_sessions_asset", "asset_id", "created_at"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("alerts.id"), unique=True
    )
    document_id: Mapped[str | None]
    document_version: Mapped[str | None]
    state: Mapped[str] = mapped_column(default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "request_id"),
        Index("ix_messages_session", "session_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("troubleshooting_sessions.id"))
    request_id: Mapped[str]
    user_text: Mapped[str]
    state: Mapped[str] = mapped_column(default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    response: Mapped[dict | None] = mapped_column(J, nullable=True)
    error: Mapped[str | None]
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Evidence(Base):
    __tablename__ = "retrieved_evidence"
    __table_args__ = (UniqueConstraint("message_id", "chunk_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("ai_document_chunks.id"))
    snapshot: Mapped[dict] = mapped_column(J)


class Step(Base):
    __tablename__ = "troubleshooting_steps"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("troubleshooting_sessions.id"))
    message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    instruction: Mapped[dict] = mapped_column(J)
    state: Mapped[str] = mapped_column(default="recommended")


class Feedback(Base):
    __tablename__ = "troubleshooting_feedback"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("troubleshooting_sessions.id"))
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("alerts.id"))
    step_id: Mapped[str | None] = mapped_column(ForeignKey("troubleshooting_steps.id"))
    kind: Mapped[str]
    text: Mapped[str]
    provenance: Mapped[str] = mapped_column(default="operator_reported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Outbox(Base):
    __tablename__ = "ai_event_outbox"
    __table_args__ = (Index("ix_outbox_delivery", "delivered", "created_at"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    event_type: Mapped[str]
    payload: Mapped[dict] = mapped_column(J)
    delivered: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def emit(db, asset_id, event_type, payload):
    db.add(Outbox(asset_id=asset_id, event_type=event_type, payload=payload))

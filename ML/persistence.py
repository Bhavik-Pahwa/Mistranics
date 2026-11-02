"""Additive integration models sharing the backend's existing database metadata."""

from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db import Base, J, now, uid


class ProcessingCheckpoint(Base):
    __tablename__ = "ml_processed_windows"
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("sensor_readings.id"), primary_key=True
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"
    __table_args__ = (
        UniqueConstraint("result_id", "finding_key"),
        Index("ix_anomaly_incident", "incident_id", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    result_id: Mapped[str] = mapped_column(ForeignKey("detector_results.id"))
    incident_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"))
    finding_key: Mapped[str]
    parameter: Mapped[str]
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(J)

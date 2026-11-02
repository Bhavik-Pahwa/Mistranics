import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    DateTime,
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    Index,
    Boolean,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid.uuid4())


J = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class PolicyRecord(Base):
    __tablename__ = "policy_versions"
    version: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(J)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class Asset(Base):
    __tablename__ = "assets"
    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    metadata_json: Mapped[dict] = mapped_column("metadata", J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Reading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        UniqueConstraint("asset_id", "window_id"),
        Index("ix_readings_event", "asset_id", "measured_at", "window_id"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    device_id: Mapped[str]
    window_id: Mapped[str]
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    schema_version: Mapped[str]
    quality_status: Mapped[str]
    operating_context: Mapped[dict] = mapped_column(J)
    readings: Mapped[list] = mapped_column(J)
    original: Mapped[dict] = mapped_column(J)


class Result(Base):
    __tablename__ = "detector_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "window_id"],
            ["sensor_readings.asset_id", "sensor_readings.window_id"],
        ),
        UniqueConstraint("asset_id", "window_id", "detector", "run_id"),
        Index("ix_results_asset_time", "asset_id", "evaluated_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    window_id: Mapped[str]
    run_id: Mapped[str]
    detector: Mapped[str]
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str]
    schema_version: Mapped[str]
    model_version: Mapped[str | None]
    config_version: Mapped[str | None]
    feature_schema_version: Mapped[str | None]
    payload: Mapped[dict] = mapped_column(J)


class Decision(Base):
    __tablename__ = "anomaly_decisions"
    __table_args__ = (
        UniqueConstraint("asset_id", "window_id", "policy_version"),
        Index("ix_decisions_asset_time", "asset_id", "decided_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    window_id: Mapped[str]
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    final_status: Mapped[str]
    policy_version: Mapped[str]
    evidence: Mapped[list] = mapped_column(J)
    decision_reason: Mapped[dict] = mapped_column(J)
    alert_processed: Mapped[bool] = mapped_column(Boolean, default=False)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    decision_id: Mapped[str] = mapped_column(ForeignKey("anomaly_decisions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str]
    severity: Mapped[str | None]
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", J, default=dict)


Index(
    "uq_active_machine_incident",
    Alert.asset_id,
    unique=True,
    postgresql_where=Alert.status.in_(["active", "acknowledged"]),
    sqlite_where=Alert.status.in_(["active", "acknowledged"]),
)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"))
    event_type: Mapped[str]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    details: Mapped[dict] = mapped_column(J)


def connect(url):
    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        **(
            {"connect_args": {"options": "-c timezone=UTC"}}
            if url.startswith("postgresql")
            else {}
        ),
    )
    return engine, sessionmaker(engine, expire_on_commit=False)

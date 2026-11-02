"""Classical ML adapter driven by the existing backend worker; no MQTT or extra loop."""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, case
from pydantic import BaseModel, Field
from backend.app.db import Reading, Decision, Alert, AlertEvent, now
from backend.app.services import lock_asset, aware, accept_result
from ML.models.telemetry import ValidatedTelemetryRecord, OperatingContext
from ML.models.limits import ManufacturerLimitRecord
from ML.pipeline import MachineHealthPipeline
from ML.shared.history_buffer import HistoryBuffer
from ML.persistence import ProcessingCheckpoint, AnomalyEvent

log = logging.getLogger(__name__)


class IncidentPolicy(BaseModel):
    version: str = "prototype-parameter-v1"
    correlation_seconds: int = Field(120, ge=3)
    recovery_observations: int = Field(3, ge=2)
    recovery_seconds: int = Field(6, ge=3)
    max_observation_gap_seconds: float = Field(4.5, ge=3)
    parameter_groups: dict[str, str] = Field(default_factory=dict)


class Runtime:
    def __init__(self, settings):
        self.pipeline = MachineHealthPipeline()
        self.policy = (
            IncidentPolicy.model_validate_json(
                Path(settings.ml_incident_policy_file).read_text()
            )
            if settings.ml_incident_policy_file
            else IncidentPolicy()
        )
        self.limits = []
        if settings.ml_limits_file:
            self.limits = [
                ManufacturerLimitRecord.model_validate(x)
                for x in json.loads(Path(settings.ml_limits_file).read_text())
            ]
            for limit in self.limits:
                if limit.status.value == "approved" and (
                    not limit.reviewer
                    or not limit.approved_at
                    or limit.approved_at.tzinfo is None
                ):
                    raise ValueError(
                        "Approved runtime limits require reviewer and timezone-aware approved_at attribution"
                    )
            self.pipeline.detector_a.limits_engine.load_limits(self.limits)
            self.pipeline.detector_a.limits_engine.config_version = (
                "limits-sha256:"
                + hashlib.sha256(
                    Path(settings.ml_limits_file).read_bytes()
                ).hexdigest()[:16]
            )
        if settings.ml_model_file:
            try:
                self.pipeline.detector_b.load_model(settings.ml_model_file)
            except Exception:
                log.error(
                    "Configured ML model could not be loaded; Detector A remains available"
                )

    def step(self, factory, ai_enabled=False):
        with factory.begin() as db:
            rows = db.scalars(
                select(Reading)
                .where(
                    ~select(ProcessingCheckpoint.reading_id)
                    .where(ProcessingCheckpoint.reading_id == Reading.id)
                    .exists()
                )
                .order_by(Reading.ingested_at, Reading.id)
                .limit(25)
            ).all()
            for row in rows:
                lock_asset(db, row.asset_id)
                if db.get(ProcessingCheckpoint, row.id):
                    continue
                records = db.scalars(
                    select(Reading)
                    .where(
                        Reading.asset_id == row.asset_id,
                        Reading.measured_at
                        >= aware(row.measured_at) - timedelta(seconds=60),
                        Reading.measured_at <= row.measured_at,
                    )
                    .order_by(Reading.measured_at, Reading.window_id)
                    .limit(1000)
                ).all()
                history = HistoryBuffer()
                for record in records:
                    history.add(canonical(record))
                current = canonical(row)
                output = self.pipeline.evaluate_record(current, history)
                results = []
                for envelope in output.all_detector_results:
                    data = envelope.model_dump(mode="json")
                    data["run_id"] = f"classical:{row.id}:{self.policy.version}"
                    data["config_version"] = data["config_version"] or (
                        "unavailable"
                        if data["detector"] != "isolation_forest"
                        else None
                    )
                    if data["detector"] == "isolation_forest":
                        data["model_version"] = data["model_version"] or "unavailable"
                        data["feature_schema_version"] = (
                            data["feature_schema_version"] or "features-1.0"
                        )
                    data["source_metadata"] = {
                        "metrics": data.pop("metrics"),
                        "skipped_reasons": data.pop("skipped_reasons"),
                    }
                    persisted, _ = accept_result(db, data)
                    results.append(persisted)
                self.aggregate(db, row, results, ai_enabled)
                db.add(ProcessingCheckpoint(reading_id=row.id))

    def aggregate(self, db, row, results, ai_enabled):
        from AI.models import emit, Session

        policy = self.policy
        abnormal = [
            (result, finding)
            for result in results
            if result.status == "completed"
            for finding in result.payload["findings"]
            if finding.get("kind") == "machine_condition"
        ]
        status = (
            "anomaly"
            if abnormal
            else (
                "normal"
                if all(r.status == "completed" for r in results)
                and row.quality_status == "valid"
                else "indeterminate"
            )
        )
        decision = Decision(
            asset_id=row.asset_id,
            window_id=row.window_id,
            policy_version="classical:" + policy.version,
            final_status=status,
            evidence=[{"result_id": r.id, "payload": r.payload} for r in results],
            decision_reason={
                "rule_id": "independent-findings",
                "policy": policy.model_dump(),
            },
            alert_processed=True,
        )
        db.add(decision)
        db.flush()
        affected = set()
        at = aware(row.measured_at)
        for result, finding in abnormal:
            parameter = finding.get("parameter") or "__multivariate__"
            key = policy.parameter_groups.get(parameter, parameter)
            affected.add(key)
            # Do not correlate unrelated parameters or observations outside the configured interval.
            candidates = db.scalars(
                select(Alert)
                .where(Alert.asset_id == row.asset_id, Alert.incident_key == key)
                .order_by(
                    case((Alert.status.in_(["active", "acknowledged"]), 0), else_=1),
                    Alert.created_at.desc(),
                )
                .limit(1)
            ).all()
            historical_only = False
            preserve_state = False
            alert = candidates[0] if candidates else None
            if alert and alert.metadata_json.get("condition_state") == "CLOSED":
                alert = None
            if alert:
                last = aware(
                    datetime.fromisoformat(alert.metadata_json["last_detected_at"])
                )
                if (at - last).total_seconds() < -policy.correlation_seconds:
                    historical_only = True
                    alert = None
                elif alert.status == "resolved" and at <= aware(
                    datetime.fromisoformat(alert.metadata_json["last_observation_at"])
                ):
                    preserve_state = True
                elif abs((at - last).total_seconds()) > policy.correlation_seconds:
                    if alert.status != "resolved":
                        # Close an old uncorrelated incident explicitly, preserving its evidence.
                        alert.status, alert.resolved_at = "resolved", now()
                        alert.metadata_json = {
                            **alert.metadata_json,
                            "condition_state": "CLOSED",
                            "closure_reason": "correlation_expired",
                        }
                        emit(
                            db,
                            row.asset_id,
                            "incident.updated",
                            {"incident_id": alert.id, "state": "CLOSED"},
                        )
                        db.flush()
                    alert = None
            created = alert is None
            previous_state = None if created else alert.metadata_json["condition_state"]
            if created:
                alert = Alert(
                    asset_id=row.asset_id,
                    decision_id=decision.id,
                    incident_key=key,
                    status="resolved" if historical_only else "active",
                    resolved_at=now() if historical_only else None,
                    severity=None,
                    metadata_json={
                        "condition_state": "ACTIVE",
                        "first_detected_at": at.isoformat(),
                        "last_detected_at": at.isoformat(),
                        "observation_count": 0,
                        "detectors": [],
                        "parameters": [],
                        "normal_count": 0,
                        "last_observation_at": at.isoformat(),
                        "policy": policy.model_dump(),
                    },
                )
                db.add(alert)
                db.flush()
            meta = dict(alert.metadata_json)
            meta.update(
                condition_state="CLOSED"
                if historical_only
                else previous_state
                if preserve_state
                else "ACTIVE",
                normal_count=meta["normal_count"] if preserve_state else 0,
                last_observation_at=max(
                    at, aware(datetime.fromisoformat(meta["last_observation_at"]))
                ).isoformat(),
                last_detected_at=max(
                    at, aware(datetime.fromisoformat(meta["last_detected_at"]))
                ).isoformat(),
                observation_count=meta["observation_count"] + 1,
                detectors=sorted(set(meta["detectors"] + [result.detector])),
                parameters=sorted(set(meta["parameters"] + [parameter])),
            )
            source_category = finding.get("limit_category")
            if (
                result.detector == "manufacturer_limits"
                and source_category
                and at >= aware(datetime.fromisoformat(meta["last_detected_at"]))
            ):
                # Preserve the manufacturer's category, never infer severity from ML score.
                alert.severity = source_category
            if (
                result.detector != "isolation_forest"
                and finding.get("observed_value") is not None
                and at >= aware(datetime.fromisoformat(meta["last_detected_at"]))
            ):
                previous = meta.get("last_values", {}).get(parameter)
                value = finding["observed_value"]
                meta["trend"] = (
                    "UNKNOWN"
                    if previous is None
                    else (
                        "INCREASING"
                        if value > previous
                        else "DECREASING"
                        if value < previous
                        else "UNCHANGED"
                    )
                )
                meta["last_values"] = {**meta.get("last_values", {}), parameter: value}
            if historical_only:
                meta["closure_reason"] = "late_historical_evidence"
                alert.status, alert.resolved_at = "resolved", now()
            elif not preserve_state:
                alert.status, alert.resolved_at = (
                    ("acknowledged" if alert.acknowledged_at else "active"),
                    None,
                )
            alert.metadata_json = meta
            db.add(
                AnomalyEvent(
                    result_id=result.id,
                    incident_id=alert.id,
                    finding_key=finding["finding_id"],
                    parameter=parameter,
                    observed_at=at,
                    evidence={
                        "detector": result.detector,
                        "finding": finding,
                        "window_id": row.window_id,
                    },
                )
            )
            db.add(
                AlertEvent(
                    alert_id=alert.id,
                    event_type="observation",
                    details={
                        "decision_id": decision.id,
                        "result_id": result.id,
                        "parameter": parameter,
                    },
                )
            )
            if created or previous_state != meta["condition_state"]:
                emit(
                    db,
                    row.asset_id,
                    "anomaly.detected"
                    if created and not historical_only
                    else "incident.updated",
                    {
                        "incident_id": alert.id,
                        "decision_id": decision.id,
                        "state": meta["condition_state"],
                        "parameter": key,
                    },
                )
            if created and ai_enabled and not historical_only:
                session = Session(asset_id=row.asset_id, incident_id=alert.id)
                db.add(session)
                db.flush()
                emit(
                    db,
                    row.asset_id,
                    "troubleshooting.started",
                    {"session_id": session.id, "incident_id": alert.id},
                )
        # Recovery requires completed, reliable evidence from every contributing detector.
        active = db.scalars(
            select(Alert).where(
                Alert.asset_id == row.asset_id,
                Alert.status.in_(["active", "acknowledged"]),
                Alert.incident_key != "__machine__",
            )
        ).all()
        by_detector = {r.detector: r for r in results}
        for alert in active:
            if alert.incident_key in affected:
                continue
            meta = dict(alert.metadata_json)
            previous_at = datetime.fromisoformat(
                meta.get("last_observation_at", meta["last_detected_at"])
            )
            if at <= aware(previous_at):
                continue  # Late/repeated observations cannot advance recovery.
            if (
                at - aware(previous_at)
            ).total_seconds() > policy.max_observation_gap_seconds:
                meta["normal_count"] = 0
            known_parameters = {
                r["parameter"]
                for r in row.readings
                if r["quality"] == "valid" and r["value_normalized"] is not None
            }
            parameters_present = all(
                p == "__multivariate__" or p in known_parameters
                for p in meta["parameters"]
            )
            reliable = (
                parameters_present
                and row.quality_status == "valid"
                and all(
                    name in by_detector
                    and by_detector[name].status == "completed"
                    and by_detector[name].payload["data_quality"]["status"] == "valid"
                    for name in meta["detectors"]
                )
            )
            if not reliable:
                meta.update(normal_count=0, last_observation_at=at.isoformat())
                alert.metadata_json = meta
                continue
            first = (
                at
                if not meta["normal_count"]
                else datetime.fromisoformat(meta["recovery_started_at"])
            )
            meta.update(
                normal_count=meta["normal_count"] + 1,
                recovery_started_at=first.isoformat(),
                last_observation_at=at.isoformat(),
            )
            old = meta["condition_state"]
            meta["condition_state"] = "RECOVERING"
            if (
                meta["normal_count"] >= policy.recovery_observations
                and (at - aware(first)).total_seconds() >= policy.recovery_seconds
            ):
                meta["condition_state"] = "RESOLVED"
                alert.status, alert.resolved_at = "resolved", now()
            alert.metadata_json = meta
            db.add(
                AlertEvent(
                    alert_id=alert.id,
                    event_type="recovery_observation",
                    details={"decision_id": decision.id, "count": meta["normal_count"]},
                )
            )
            if old != meta["condition_state"]:
                emit(
                    db,
                    row.asset_id,
                    "incident.resolved"
                    if alert.status == "resolved"
                    else "incident.updated",
                    {"incident_id": alert.id, "state": meta["condition_state"]},
                )
                if ai_enabled:
                    emit(
                        db,
                        row.asset_id,
                        "troubleshooting.resolution_updated",
                        {"incident_id": alert.id, "state": meta["condition_state"]},
                    )


def canonical(row):
    context = dict(row.operating_context)
    if "load_pct" in context and "load_percentage" not in context:
        context["load_percentage"] = context["load_pct"]
    return ValidatedTelemetryRecord(
        machine_id=row.asset_id,
        device_id=row.device_id,
        window_id=row.window_id,
        schema_version=row.schema_version,
        measured_at=aware(row.measured_at),
        window_start=aware(row.window_start),
        window_end=aware(row.window_end),
        received_at=row.received_at,
        ingested_at=aware(row.ingested_at),
        readings=row.readings,
        quality_status=row.quality_status,
        operating_context=OperatingContext.model_validate(context),
    )

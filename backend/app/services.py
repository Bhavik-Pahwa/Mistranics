"""Transport-independent persistence, policy evaluation, and incident lifecycle."""

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from .db import Asset, Reading, Result, Decision, Alert, AlertEvent, PolicyRecord, now
from .schemas import Telemetry, DetectorResult

log = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(self, detail, status=422):
        self.detail, self.status = detail, status


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def load_registry(path):
    registry = json.loads(Path(path).read_text())
    for asset in registry:
        if (
            not asset.get("asset_id")
            or not asset.get("devices")
            or not asset.get("sensors")
        ):
            raise ValueError("registry requires asset_id, devices and sensors")
        for sensor in asset["sensors"]:
            for conversion in sensor.get("units", {}).values():
                if not all(
                    math.isfinite(conversion.get(k, default))
                    for k, default in [("scale", 1), ("offset", 0)]
                ):
                    raise ValueError("non-finite unit conversion")
    return registry


def seed(session, registry):
    for config in registry:
        asset = session.get(Asset, config["asset_id"])
        if not asset:
            session.add(
                Asset(
                    asset_id=config["asset_id"],
                    name=config.get("name", config["asset_id"]),
                    metadata_json=config,
                )
            )
        else:
            asset.name = config.get("name", config["asset_id"])
            asset.metadata_json = config


def register_policy(session, policy):
    if not policy:
        return
    payload = policy.model_dump(mode="json")
    existing = session.get(PolicyRecord, policy.version)
    if existing and existing.payload != payload:
        raise ValueError("Policy version is immutable; use a new version")
    if not existing:
        session.add(PolicyRecord(version=policy.version, payload=payload))


def lock_asset(session, asset_id):
    asset = session.scalar(
        select(Asset).where(Asset.asset_id == asset_id).with_for_update()
    )
    if not asset:
        raise DomainError("Unknown asset", 404)
    return asset


def ingest(session, payload):
    message = Telemetry.model_validate(payload)
    asset = lock_asset(session, message.machine_id)
    if message.device_id not in asset.metadata_json["devices"]:
        raise DomainError("Unknown device for asset")
    original = message.model_dump(mode="json")
    existing = session.scalar(
        select(Reading).where(
            Reading.asset_id == message.machine_id,
            Reading.window_id == message.reading_id,
        )
    )
    if existing:
        if existing.original != original:
            raise DomainError("Window identity reused with different content", 409)
        log.info(
            "duplicate telemetry machine=%s window=%s",
            message.machine_id,
            message.reading_id,
        )
        return existing, True
    canonical = []
    for r in message.readings:
        sensor = next(
            (
                s
                for s in asset.metadata_json["sensors"]
                if s["sensor_id"] == r.sensor_id and s["parameter"] == r.parameter
            ),
            None,
        )
        if not sensor:
            raise DomainError("Unknown sensor/parameter")
        conversion = sensor.get("units", {}).get(r.unit)
        quality = r.quality
        if conversion is None:
            quality = "missing" if quality == "missing" else "suspect"
            value, unit = None, None
        else:
            value = (
                None
                if r.value is None
                else r.value * conversion.get("scale", 1) + conversion.get("offset", 0)
            )
            unit = conversion["canonical_unit"]
            if value is not None and not math.isfinite(value):
                raise DomainError("Conversion overflow")
        canonical.append(
            dict(
                sensor_id=r.sensor_id,
                parameter=r.parameter,
                value_original=r.value,
                unit_original=r.unit,
                value_normalized=value,
                unit_normalized=unit,
                quality=quality,
            )
        )
    row = Reading(
        asset_id=message.machine_id,
        device_id=message.device_id,
        window_id=message.reading_id,
        measured_at=message.measured_at,
        window_start=message.window_start,
        window_end=message.window_end,
        received_at=message.received_at,
        schema_version=message.schema_version,
        operating_context=message.operating_context,
        readings=canonical,
        original=original,
        quality_status="valid"
        if all(r["quality"] == "valid" for r in canonical)
        else "suspect",
    )
    session.add(row)
    session.flush()
    log.info("telemetry accepted machine=%s window=%s", row.asset_id, row.window_id)
    return row, False


def accept_result(session, payload):
    message = DetectorResult.model_validate(payload)
    lock_asset(session, message.machine_id)
    reading = session.scalar(
        select(Reading).where(
            Reading.asset_id == message.machine_id,
            Reading.window_id == message.window_id,
        )
    )
    if not reading:
        raise DomainError("Unknown machine/window reference", 404)
    original = message.model_dump(mode="json")
    existing = session.scalar(
        select(Result).where(
            Result.asset_id == message.machine_id,
            Result.window_id == message.window_id,
            Result.detector == message.detector,
            Result.run_id == message.run_id,
        )
    )
    if existing:
        if existing.payload != original:
            raise DomainError("Run identity reused with different content", 409)
        return existing, True
    row = Result(
        asset_id=message.machine_id,
        window_id=message.window_id,
        run_id=message.run_id,
        detector=message.detector,
        evaluated_at=message.evaluated_at,
        status=message.status,
        schema_version=message.schema_version,
        model_version=message.model_version,
        config_version=message.config_version,
        feature_schema_version=message.feature_schema_version,
        payload=original,
    )
    session.add(row)
    session.flush()
    log.info(
        "detector result accepted machine=%s window=%s result=%s",
        row.asset_id,
        row.window_id,
        row.id,
    )
    return row, False


def event(session, alert, kind, details):
    session.add(AlertEvent(alert_id=alert.id, event_type=kind, details=details))
    log.info("alert transition alert=%s event=%s", alert.id, kind)


def apply_alert(session, decision, policy):
    if decision.alert_processed or not policy.alerts_enabled:
        return
    lock_asset(session, decision.asset_id)
    alert = session.scalar(
        select(Alert)
        .where(
            Alert.asset_id == decision.asset_id,
            Alert.status.in_(["active", "acknowledged"]),
        )
        .with_for_update()
    )
    reading = session.scalar(
        select(Reading).where(
            Reading.asset_id == decision.asset_id,
            Reading.window_id == decision.window_id,
        )
    )
    event_time = aware(reading.measured_at)
    if decision.final_status == "anomaly":
        if not alert:
            alert = Alert(
                asset_id=decision.asset_id,
                decision_id=decision.id,
                status="active",
                severity=policy.severity,
                metadata_json={
                    "policy_version": policy.version,
                    "latest_anomaly_at": event_time.isoformat(),
                },
            )
            session.add(alert)
            session.flush()
            event(session, alert, "created", {"decision_id": decision.id})
        else:
            latest = datetime.fromisoformat(alert.metadata_json["latest_anomaly_at"])
            if event_time > latest:
                alert.metadata_json = {
                    **alert.metadata_json,
                    "latest_anomaly_at": event_time.isoformat(),
                }
            event(session, alert, "updated", {"decision_id": decision.id})
    elif decision.final_status == "normal" and alert and policy.resolve_on_normal:
        # Late historical normal windows must not resolve a newer incident.
        if event_time > datetime.fromisoformat(
            alert.metadata_json["latest_anomaly_at"]
        ):
            alert.status, alert.resolved_at = "resolved", now()
            event(
                session,
                alert,
                "resolved",
                {"decision_id": decision.id, "actor": "policy"},
            )
    decision.alert_processed = True


def evaluate(session, reading, policy):
    """First evaluation per detector is frozen; late results remain evidence-only."""
    lock_asset(session, reading.asset_id)
    existing = session.scalar(
        select(Decision).where(
            Decision.asset_id == reading.asset_id,
            Decision.window_id == reading.window_id,
            Decision.policy_version == policy.version,
        )
    )
    if existing:
        apply_alert(session, existing, policy)
        return existing
    first = {}
    for detector in policy.required_detectors:
        row = session.scalar(
            select(Result)
            .where(
                Result.asset_id == reading.asset_id,
                Result.window_id == reading.window_id,
                Result.detector == detector,
            )
            .order_by(Result.received_at, Result.id)
            .limit(1)
        )
        if row:
            first[detector] = row
    complete = set(first) == set(policy.required_detectors)
    if (
        not complete
        and (now() - aware(reading.ingested_at)).total_seconds()
        < policy.timeout_seconds
    ):
        return None
    status, reason = "normal", {"rule_id": "completed_no_findings"}
    if not complete or any(r.status != "completed" for r in first.values()):
        status, reason = (
            "indeterminate",
            {
                "rule_id": "missing_or_failed_evaluation",
                "missing": sorted(set(policy.required_detectors) - set(first)),
            },
        )
    findings = [
        (r, f)
        for r in first.values()
        if r.status == "completed"
        for f in r.payload["findings"]
    ]
    # Only explicit machine-condition findings can create mechanical incidents.
    matched = False
    for rule in policy.rules:
        if any(
            r.detector == rule.detector
            and f.get("kind") == "machine_condition"
            and all(
                k in f and type(f[k]) is type(v) and f[k] == v
                for k, v in rule.match.items()
            )
            for r, f in findings
        ):
            if rule.outcome == "anomaly":
                status, reason, matched = "anomaly", {"rule_id": rule.id}, True
                break
            status, reason, matched = "indeterminate", {"rule_id": rule.id}, True
    if findings and not matched and status == "normal":
        status, reason = "indeterminate", {"rule_id": "unmapped_findings"}
    if (
        any(r.payload["data_quality"].get("status") != "valid" for r in first.values())
        and status == "normal"
    ):
        status, reason = "indeterminate", {"rule_id": "data_quality"}
    if reading.quality_status != "valid" and status == "normal":
        status, reason = "indeterminate", {"rule_id": "telemetry_quality"}
    decision = Decision(
        asset_id=reading.asset_id,
        window_id=reading.window_id,
        final_status=status,
        policy_version=policy.version,
        evidence=[{"result_id": r.id, "payload": r.payload} for r in first.values()],
        decision_reason={**reason, "policy": policy.model_dump(mode="json")},
    )
    session.add(decision)
    session.flush()
    apply_alert(session, decision, policy)
    log.info(
        "decision machine=%s window=%s decision=%s status=%s",
        reading.asset_id,
        reading.window_id,
        decision.id,
        status,
    )
    return decision


def process_pending(factory, policy, batch=100):
    if not policy:
        return
    # Persistent eligibility from telemetry/results; safe after process crashes.
    with factory.begin() as session:
        pending = session.scalars(
            select(Reading)
            .where(
                ~select(Decision.id)
                .where(
                    Decision.asset_id == Reading.asset_id,
                    Decision.window_id == Reading.window_id,
                    Decision.policy_version == policy.version,
                )
                .exists()
            )
            .order_by(Reading.ingested_at)
            .limit(batch)
        ).all()
        for reading in pending:
            evaluate(session, reading, policy)
        decisions = session.scalars(
            select(Decision)
            .where(
                Decision.policy_version == policy.version,
                Decision.alert_processed == False,
            )
            .limit(batch)
        ).all()
        for decision in decisions:
            apply_alert(session, decision, policy)


def transition(session, alert_id, action, reason, policy):
    candidate = session.get(Alert, alert_id)
    if not candidate:
        raise DomainError("Unknown alert", 404)
    lock_asset(session, candidate.asset_id)
    alert = session.scalar(
        select(Alert)
        .where(Alert.id == alert_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if alert.incident_key != "__machine__":
        if action != "acknowledge" or alert.status != "active":
            raise DomainError(
                "Condition recovery is evidence-driven; only active incident acknowledgment is allowed here",
                409,
            )
        alert.status, alert.acknowledged_at = "acknowledged", now()
        event(session, alert, "acknowledged", {"actor": "operator", "reason": reason})
        return alert
    if not policy or not policy.alerts_enabled:
        raise DomainError("Alert policy unavailable", 409)
    if action == "acknowledge":
        if alert.status != "active":
            raise DomainError("Only active alerts can be acknowledged", 409)
        alert.status, alert.acknowledged_at = "acknowledged", now()
    else:
        if not policy.manual_resolution or alert.status not in (
            "active",
            "acknowledged",
        ):
            raise DomainError("Resolution disallowed by policy or state", 409)
        alert.status, alert.resolved_at = "resolved", now()
    event(
        session,
        alert,
        "acknowledged" if action == "acknowledge" else "resolved",
        {"actor": "operator", "reason": reason},
    )
    return alert

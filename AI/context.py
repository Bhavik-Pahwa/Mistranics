from datetime import timedelta
from sqlalchemy import select
from backend.app.db import Asset, Reading, Alert, now
from backend.app.services import aware
from .models import Feedback


def plan(question):
    q = question.casefold()
    result = {"configuration"}
    if any(
        term in q
        for term in [
            "current",
            "now",
            "reading",
            "sensor",
            "temperature",
            "pressure",
            "vibration",
            "why",
            "increas",
            "improv",
            "intervention",
            "work",
            "recover",
        ]
    ):
        result.add("readings")
    if any(
        term in q
        for term in [
            "why",
            "increas",
            "trend",
            "improv",
            "intervention",
            "work",
            "recent",
        ]
    ):
        result.add("history")
    if any(term in q for term in ["limit", "maximum", "minimum", "threshold", "why"]):
        result.add("limits")
    if any(
        term in q
        for term in [
            "incident",
            "before",
            "history",
            "happened",
            "why",
            "fault",
            "anomal",
            "recover",
            "improv",
            "work",
        ]
    ):
        result.add("incidents")
    if any(
        term in q
        for term in [
            "manual",
            "procedure",
            "inspect",
            "check",
            "fix",
            "repair",
            "cause",
            "why",
            "troubleshoot",
            "instruction",
        ]
    ):
        result.add("manual")
    if result == {"configuration"}:
        result.add("manual")
    return result


def assemble(db, session, question, settings, limits):
    selected = plan(question)
    asset = db.get(Asset, session.asset_id)
    context = {
        "machine": {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "configuration": asset.metadata_json,
        },
        "selected_context": sorted(selected),
        "references": [],
        "limitations": [],
    }
    if "readings" in selected:
        latest = db.scalar(
            select(Reading)
            .where(Reading.asset_id == asset.asset_id)
            .order_by(Reading.measured_at.desc(), Reading.window_id.desc())
            .limit(1)
        )
        if not latest:
            context["limitations"].append("No telemetry is available")
            context["telemetry_stale"] = True
        else:
            age = (now() - aware(latest.measured_at)).total_seconds()
            context["telemetry_stale"] = (
                age > settings.ai_stale_seconds
                or age < -3
                or context.get("mqtt_connected") is False
            )
            context["latest_reading"] = reading_json(latest)
            context["references"].append("reading:" + latest.id)
            if context["telemetry_stale"]:
                context["limitations"].append(
                    "Telemetry is stale or has an invalid future observation time; do not describe it as current"
                )
            if "history" in selected:
                rows = db.scalars(
                    select(Reading)
                    .where(
                        Reading.asset_id == asset.asset_id,
                        Reading.measured_at
                        >= aware(latest.measured_at) - timedelta(seconds=60),
                        Reading.measured_at <= latest.measured_at,
                    )
                    .order_by(Reading.measured_at, Reading.window_id)
                    .limit(50)
                ).all()
                context["recent_history"] = [reading_json(row) for row in rows]
                context["references"].extend("reading:" + row.id for row in rows)
    if "limits" in selected:
        applicable = [
            limit
            for limit in limits
            if limit.machine_id == asset.asset_id and limit.status.value == "approved"
        ]
        context["approved_limits"] = [
            limit.model_dump(mode="json") for limit in applicable
        ]
        context["references"].extend("limit:" + limit.limit_id for limit in applicable)
        if not applicable:
            context["limitations"].append(
                "Approved limits are unavailable; documentation is not an authoritative limit configuration"
            )
    if "incidents" in selected or session.incident_id:
        stmt = select(Alert).where(Alert.asset_id == asset.asset_id)
        if session.incident_id:
            stmt = stmt.where(Alert.id == session.incident_id)
        rows = db.scalars(stmt.order_by(Alert.created_at.desc()).limit(10)).all()
        context["incidents"] = [
            {
                "incident_id": row.id,
                "status": row.metadata_json.get("condition_state", row.status),
                "severity": row.severity,
                "acknowledged": row.acknowledged_at is not None,
                "evidence": row.metadata_json,
            }
            for row in rows
        ]
        context["references"].extend("incident:" + row.id for row in rows)
    feedback = db.scalars(
        select(Feedback)
        .where(Feedback.session_id == session.id)
        .order_by(Feedback.created_at.desc())
        .limit(20)
    ).all()
    context["operator_reports"] = [
        {
            "kind": f.kind,
            "text": f.text,
            "provenance": "operator_reported",
            "verified": False,
        }
        for f in reversed(feedback)
    ]
    return context


def reading_json(row):
    return {
        "id": row.id,
        "measured_at": aware(row.measured_at).isoformat(),
        "quality_status": row.quality_status,
        "readings": row.readings,
        "operating_context": row.operating_context,
    }


def finalize_condition(answer, context, settings):
    """Render measured facts from authoritative storage rather than model paraphrases."""
    from datetime import datetime

    latest = context.get("latest_reading")
    if latest:
        measured_at = datetime.fromisoformat(latest["measured_at"])
        age = (now() - aware(measured_at)).total_seconds()
        context["telemetry_stale"] = (
            age > settings.ai_stale_seconds
            or age < -3
            or context.get("mqtt_connected") is False
        )
        observations = []
        for reading in latest["readings"][:10]:
            value, unit = reading["value_normalized"], reading["unit_normalized"]
            if value is None:
                value, unit = reading["value_original"], reading["unit_original"]
            observations.append(
                f"{reading['parameter']} ({reading['sensor_id']}): {value if value is not None else 'missing'} {unit or ''}; quality={reading['quality']}"
            )
        answer.condition_summary = (
            "Latest stored observation at "
            + latest["measured_at"]
            + ": "
            + "; ".join(observations)
            + (
                ". Telemetry is stale; this is not a current-condition confirmation."
                if context["telemetry_stale"]
                else ". Mechanical failure is not confirmed."
            )
        )
        if context["telemetry_stale"]:
            limitation = "Telemetry is stale at response time; retrieve fresh readings before assessing the current condition"
            if limitation not in context["limitations"]:
                context["limitations"].append(limitation)
            if limitation not in answer.missing_information:
                answer.missing_information.append(limitation)
            answer.response_type = "INSUFFICIENT_EVIDENCE"
        elif "manual" not in context["selected_context"] and not context["limitations"]:
            answer.response_type = "TROUBLESHOOTING"
    elif context.get("incidents"):
        answer.condition_summary = "Persisted incident evidence is attached. The mechanical cause remains unconfirmed."
    elif context.get("approved_limits"):
        answer.condition_summary = "Reviewed manufacturer configurations are attached with their applicability conditions. No current mechanical condition is inferred."
    else:
        answer.condition_summary = "No relevant current telemetry was selected or available. Use the attached documentation and stated evidence limitations."
    return answer

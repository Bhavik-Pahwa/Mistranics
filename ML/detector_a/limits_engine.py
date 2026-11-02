import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from ML.models.telemetry import ValidatedTelemetryRecord, ReadingQuality
from ML.models.limits import (
    ManufacturerLimitRecord,
    LimitVerificationStatus,
    TimeBasis,
)
from ML.models.results import (
    DetectorType,
    EvaluationStatus,
    DetectorResultEnvelope,
    Finding,
    FindingKind,
    DataQualityMetadata,
)


class ManufacturerLimitsEngine:
    """
    Detector A1: Compares validated sensor telemetry against human-approved manufacturer limits.
    Candidate, under_review, and rejected limits are strictly ignored at runtime.
    """

    def __init__(self, config_version: str = "limits-v1.0"):
        self.config_version = config_version
        # limit_id -> ManufacturerLimitRecord
        self._limits: Dict[str, ManufacturerLimitRecord] = {}

    def add_limit(self, limit: ManufacturerLimitRecord) -> None:
        self._limits[limit.limit_id] = limit

    def load_limits(self, limits: List[ManufacturerLimitRecord]) -> None:
        for lim in limits:
            self._limits[lim.limit_id] = lim

    def get_approved_limits_for_machine(self, machine_id: str) -> List[ManufacturerLimitRecord]:
        return [
            lim for lim in self._limits.values()
            if lim.machine_id == machine_id and lim.status == LimitVerificationStatus.approved
        ]

    def evaluate(self, record: ValidatedTelemetryRecord, run_id: Optional[str] = None) -> DetectorResultEnvelope:
        eval_run_id = run_id or f"run-limits-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        approved_limits = self.get_approved_limits_for_machine(record.machine_id)
        findings: List[Finding] = []
        skipped_reasons: List[str] = []

        # Check if any limits were registered but not approved
        all_machine_limits = [lim for lim in self._limits.values() if lim.machine_id == record.machine_id]
        unapproved = [lim for lim in all_machine_limits if lim.status != LimitVerificationStatus.approved]
        if unapproved and not approved_limits:
            skipped_reasons.append(
                f"No approved limits available for machine {record.machine_id} ({len(unapproved)} unapproved limit(s) ignored at runtime)"
            )

        if not all_machine_limits:
            skipped_reasons.append(f"No limits configured for machine {record.machine_id}")

        ctx = record.operating_context

        for reading in record.readings:
            # Data-quality check: missing or suspect values cannot be evaluated against limits
            if reading.quality != ReadingQuality.valid or reading.value_normalized is None:
                skipped_reasons.append(
                    f"Reading {reading.sensor_id} ({reading.parameter}) skipped due to quality status: {reading.quality}"
                )
                continue

            # Find matching approved limits for this parameter and optional sensor_id
            matching_limits = [
                lim for lim in approved_limits
                if lim.parameter.lower() == reading.parameter.lower()
                and (lim.sensor_id is None or lim.sensor_id == reading.sensor_id)
            ]

            for lim in matching_limits:
                # Check operating condition applicability
                if not lim.is_applicable(
                    state=ctx.operating_state,
                    mode=ctx.operating_mode,
                    rpm=ctx.rpm,
                    load=ctx.load_percentage,
                ):
                    skipped_reasons.append(
                        f"Limit {lim.limit_id} for {lim.parameter} does not match operating context (state={ctx.operating_state}, mode={ctx.operating_mode})"
                    )
                    continue

                val = reading.value_normalized

                # Upper limit check
                if lim.upper_limit is not None and val > lim.upper_limit:
                    excess = val - lim.upper_limit
                    findings.append(
                        Finding(
                            finding_id=f"f-lim-{uuid.uuid4().hex[:8]}",
                            rule_id=lim.limit_id,
                            parameter=reading.parameter,
                            sensor_id=reading.sensor_id,
                            kind=FindingKind.machine_condition,
                            observed_value=val,
                            threshold=lim.upper_limit,
                            direction="upper",
                            unit=reading.unit_normalized or reading.unit_original,
                            limit_category=lim.category.value,
                            evidence_time=record.measured_at,
                            source_reference=lim.source.model_dump(),
                            details={"excess": excess, "status": lim.status.value},
                        )
                    )

                # Lower limit check
                if lim.lower_limit is not None and val < lim.lower_limit:
                    shortfall = lim.lower_limit - val
                    findings.append(
                        Finding(
                            finding_id=f"f-lim-{uuid.uuid4().hex[:8]}",
                            rule_id=lim.limit_id,
                            parameter=reading.parameter,
                            sensor_id=reading.sensor_id,
                            kind=FindingKind.machine_condition,
                            observed_value=val,
                            threshold=lim.lower_limit,
                            direction="lower",
                            unit=reading.unit_normalized or reading.unit_original,
                            limit_category=lim.category.value,
                            evidence_time=record.measured_at,
                            source_reference=lim.source.model_dump(),
                            details={"shortfall": shortfall, "status": lim.status.value},
                        )
                    )

        return DetectorResultEnvelope(
            schema_version="1.0",
            detector=DetectorType.manufacturer_limits,
            machine_id=record.machine_id,
            window_id=record.window_id,
            run_id=eval_run_id,
            evaluated_at=now,
            status=EvaluationStatus.completed,
            findings=findings,
            data_quality=DataQualityMetadata(status=record.quality_status, warnings=record.quality_warnings),
            model_or_config_version=self.config_version,
            config_version=self.config_version,
            metrics={"approved_limits_checked": len(approved_limits), "violations_found": len(findings)},
            skipped_reasons=skipped_reasons,
        )


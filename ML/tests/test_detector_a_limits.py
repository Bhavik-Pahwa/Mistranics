from datetime import datetime, timezone
import pytest
from ML.models.telemetry import (
    ValidatedTelemetryRecord,
    ValidatedSensorReading,
    OperatingContext,
    ReadingQuality,
)
from ML.models.limits import (
    ManufacturerLimitRecord,
    LimitVerificationStatus,
    LimitCategory,
    SourceReference,
)
from ML.models.results import DetectorType, EvaluationStatus
from ML.detector_a.limits_engine import ManufacturerLimitsEngine


@pytest.fixture
def base_telemetry():
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    return ValidatedTelemetryRecord(
        machine_id="motor_001",
        device_id="esp32_01",
        window_id="win-101",
        measured_at=now,
        window_start=now,
        window_end=now,
        operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
        readings=[
            ValidatedSensorReading(
                sensor_id="temp_01",
                parameter="motor_temperature",
                value_original=82.0,
                unit_original="degC",
                value_normalized=82.0,
                unit_normalized="degC",
                quality=ReadingQuality.valid,
            ),
            ValidatedSensorReading(
                sensor_id="curr_01",
                parameter="mean_current",
                value_original=15.0,
                unit_original="A",
                value_normalized=15.0,
                unit_normalized="A",
                quality=ReadingQuality.valid,
            ),
        ]
    )


def test_unapproved_limit_ignored(base_telemetry):
    """Candidate or under-review limits must NEVER be applied at runtime."""
    engine = ManufacturerLimitsEngine()
    source = SourceReference(document="Manual_M1.pdf", page_or_section="p.12")
    
    # Candidate limit with upper_limit=70.0 (would be violated since temp is 82.0)
    candidate_limit = ManufacturerLimitRecord(
        limit_id="lim-candidate",
        machine_id="motor_001",
        parameter="motor_temperature",
        upper_limit=70.0,
        unit="degC",
        status=LimitVerificationStatus.candidate,
        source=source,
    )
    engine.add_limit(candidate_limit)

    result = engine.evaluate(base_telemetry)
    # Since only candidate limit exists, no approved limit was checked
    assert result.status == EvaluationStatus.completed
    assert len(result.findings) == 0
    assert any("No approved limit" in reason for reason in result.skipped_reasons)


def test_approved_limit_violation_detected(base_telemetry):
    """Approved limit that is crossed produces a structured finding."""
    engine = ManufacturerLimitsEngine()
    source = SourceReference(document="Manual_M1.pdf", revision="1.2", page_or_section="Table 4-1")
    
    approved_limit = ManufacturerLimitRecord(
        limit_id="lim-approved-01",
        machine_id="motor_001",
        parameter="motor_temperature",
        upper_limit=75.0,
        unit="degC",
        category=LimitCategory.warning,
        status=LimitVerificationStatus.approved,
        reviewer="chief_engineer_bob",
        source=source,
    )
    engine.add_limit(approved_limit)

    result = engine.evaluate(base_telemetry)
    assert result.status == EvaluationStatus.completed
    assert result.detector == DetectorType.manufacturer_limits
    assert len(result.findings) == 1
    
    finding = result.findings[0]
    assert finding.parameter == "motor_temperature"
    assert finding.observed_value == 82.0
    assert finding.threshold == 75.0
    assert finding.direction == "upper"
    assert pytest.approx(finding.details["excess"], 0.01) == 7.0
    assert finding.source_reference["document"] == "Manual_M1.pdf"
    assert finding.limit_category == "warning"


def test_operating_condition_mismatch_skips_limit(base_telemetry):
    """Limit applicable only to 'high_performance' mode should not trigger when in 'standard' mode."""
    engine = ManufacturerLimitsEngine()
    source = SourceReference(document="Manual_M1.pdf", page_or_section="p.20")
    
    limit = ManufacturerLimitRecord(
        limit_id="lim-hp",
        machine_id="motor_001",
        parameter="motor_temperature",
        upper_limit=80.0,
        unit="degC",
        applicable_mode="high_performance",  # Telemetry has "standard"
        status=LimitVerificationStatus.approved,
        source=source,
    )
    engine.add_limit(limit)

    result = engine.evaluate(base_telemetry)
    assert len(result.findings) == 0
    assert any("does not match operating context" in reason for reason in result.skipped_reasons)


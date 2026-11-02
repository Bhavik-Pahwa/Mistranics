import pytest
from datetime import datetime, timezone
from ML.models.telemetry import (
    ReadingQuality,
    SensorReading,
    OperatingContext,
    RawTelemetryPayload,
    ValidatedSensorReading,
    ValidatedTelemetryRecord,
)
from ML.models.limits import (
    LimitVerificationStatus,
    LimitCategory,
    TimeBasis,
    ManufacturerLimitRecord,
    SourceReference,
)
from ML.models.results import (
    DetectorType,
    EvaluationStatus,
    DetectorResultEnvelope,
    Finding,
    DataQualityMetadata,
)
from ML.models.features import (
    FEATURE_SCHEMA_VERSION,
    FEATURE_COLUMNS,
    FeatureSnapshot,
)

def test_telemetry_models_valid():
    now = datetime.now(timezone.utc)
    raw = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="esp32_01",
        reading_id="win-100",
        measured_at=now,
        operating_context=OperatingContext(operating_state="running", rpm=1450.0),
        readings=[
            SensorReading(sensor_id="temp_01", parameter="motor_temperature", value=55.2, unit="degC"),
            SensorReading(sensor_id="vib_01", parameter="vibration_rms", value=None, unit="mm/s", quality=ReadingQuality.missing),
        ]
    )
    assert raw.machine_id == "motor_001"
    assert raw.readings[1].value is None
    assert raw.readings[1].quality == ReadingQuality.missing

def test_manufacturer_limit_record_statuses():
    source = SourceReference(document="OEM_Manual.pdf", revision="rev2", page_or_section="p.42")
    limit = ManufacturerLimitRecord(
        limit_id="lim-1",
        machine_id="motor_001",
        parameter="motor_temperature",
        upper_limit=75.0,
        unit="degC",
        category=LimitCategory.warning,
        status=LimitVerificationStatus.candidate,
        source=source,
    )
    assert limit.status == LimitVerificationStatus.candidate
    assert limit.upper_limit == 75.0

def test_feature_columns_definition():
    assert len(FEATURE_COLUMNS) == 22
    assert "mean_temperature" in FEATURE_COLUMNS
    assert "temperature_change_15s" in FEATURE_COLUMNS
    assert "operating_state_code" in FEATURE_COLUMNS

def test_detector_result_envelope():
    now = datetime.now(timezone.utc)
    res = DetectorResultEnvelope(
        detector=DetectorType.isolation_forest,
        machine_id="motor_001",
        window_id="win-100",
        run_id="run-001",
        evaluated_at=now,
        status=EvaluationStatus.completed,
        findings=[],
        data_quality=DataQualityMetadata(status=ReadingQuality.valid),
        model_or_config_version="model-v1",
        model_version="model-v1",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
    )
    assert res.status == EvaluationStatus.completed
    assert res.detector == DetectorType.isolation_forest


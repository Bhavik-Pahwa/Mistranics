from datetime import datetime, timezone, timedelta
import pytest
from ML.models.telemetry import (
    RawTelemetryPayload,
    SensorReading,
    OperatingContext,
    ReadingQuality,
)
from ML.shared.units import normalize_unit
from ML.shared.validator import TelemetryValidator, ValidationResult
from ML.shared.history_buffer import HistoryBuffer


def test_unit_normalization():
    # Temperature °F to °C
    val, unit, ok = normalize_unit("motor_temperature", 212.0, "degF")
    assert ok is True
    assert unit == "degC"
    assert pytest.approx(val, 0.01) == 100.0

    # Pressure bar to kPa
    val, unit, ok = normalize_unit("mean_pressure", 2.0, "bar")
    assert ok is True
    assert unit == "kPa"
    assert pytest.approx(val, 0.01) == 200.0

    # Pressure psi to kPa
    val, unit, ok = normalize_unit("mean_pressure", 14.5038, "psi")
    assert ok is True
    assert unit == "kPa"
    assert pytest.approx(val, 0.1) == 100.0

    # Vibration in/s to mm/s
    val, unit, ok = normalize_unit("vibration_rms", 1.0, "in/s")
    assert ok is True
    assert unit == "mm/s"
    assert pytest.approx(val, 0.01) == 25.4

    # Missing value handling: None remains None
    val, unit, ok = normalize_unit("motor_temperature", None, "degC")
    assert val is None
    assert unit == "degC"
    assert ok is True

    # Unknown unit produces suspect
    val, unit, ok = normalize_unit("motor_temperature", 50.0, "furlongs_per_fortnight")
    assert ok is False


def test_telemetry_validator_valid():
    validator = TelemetryValidator()
    now = datetime.now(timezone.utc)
    raw = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="esp32_01",
        reading_id="win-001",
        measured_at=now,
        received_at=now + timedelta(milliseconds=150),
        operating_context=OperatingContext(operating_state="running", rpm=1500.0),
        readings=[
            SensorReading(sensor_id="temp_1", parameter="motor_temperature", value=65.0, unit="degC"),
            SensorReading(sensor_id="vib_1", parameter="vibration_rms", value=2.5, unit="mm/s"),
        ]
    )

    result = validator.validate(raw)
    assert result.is_valid is True
    record = result.validated_record
    assert record is not None
    assert record.machine_id == "motor_001"
    assert len(record.readings) == 2
    assert record.readings[0].value_normalized == 65.0
    assert record.readings[0].unit_normalized == "degC"
    assert record.readings[0].quality == ReadingQuality.valid


def test_telemetry_validator_partial_sensor_failure():
    """A bad value from one sensor must not discard valid readings from other sensors."""
    validator = TelemetryValidator()
    now = datetime.now(timezone.utc)
    raw = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="esp32_01",
        reading_id="win-002",
        measured_at=now,
        readings=[
            SensorReading(sensor_id="temp_1", parameter="motor_temperature", value=65.0, unit="degC"),
            SensorReading(sensor_id="vib_1", parameter="vibration_rms", value=None, unit="mm/s", quality=ReadingQuality.missing),
        ]
    )

    result = validator.validate(raw)
    assert result.is_valid is True
    record = result.validated_record
    assert record.readings[0].quality == ReadingQuality.valid
    assert record.readings[1].quality == ReadingQuality.missing
    assert record.readings[1].value_normalized is None


def test_history_buffer_deduplication_and_ordering():
    buffer = HistoryBuffer(late_threshold_seconds=15.0)
    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Ingest window 1
    validator = TelemetryValidator()
    raw1 = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="dev1",
        reading_id="w-1",
        measured_at=t0,
        readings=[SensorReading(sensor_id="s1", parameter="motor_temperature", value=50.0, unit="degC")]
    )
    rec1 = validator.validate(raw1).validated_record
    status1 = buffer.add(rec1)
    assert status1.is_duplicate is False
    assert status1.is_late is False

    # 2. Duplicate window 1
    status_dup = buffer.add(rec1)
    assert status_dup.is_duplicate is True

    # 3. Ingest window 2 (t0 + 3s)
    raw2 = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="dev1",
        reading_id="w-2",
        measured_at=t0 + timedelta(seconds=3),
        readings=[SensorReading(sensor_id="s1", parameter="motor_temperature", value=51.0, unit="degC")]
    )
    rec2 = validator.validate(raw2).validated_record
    buffer.add(rec2)

    # 4. Out-of-order but within latency (t0 + 1.5s)
    raw_ooo = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="dev1",
        reading_id="w-ooo",
        measured_at=t0 + timedelta(seconds=1.5),
        readings=[SensorReading(sensor_id="s1", parameter="motor_temperature", value=50.5, unit="degC")]
    )
    rec_ooo = validator.validate(raw_ooo).validated_record
    status_ooo = buffer.add(rec_ooo)
    assert status_ooo.is_duplicate is False
    assert status_ooo.is_late is False

    # Check order in buffer
    records = buffer.get_recent_history("motor_001", seconds=10, as_of=t0 + timedelta(seconds=3))
    timestamps = [r.measured_at for r in records]
    assert timestamps == sorted(timestamps)

    # 5. Very late reading (older than 15s)
    raw_late = RawTelemetryPayload(
        machine_id="motor_001",
        device_id="dev1",
        reading_id="w-late",
        measured_at=t0 - timedelta(seconds=20),
        readings=[SensorReading(sensor_id="s1", parameter="motor_temperature", value=40.0, unit="degC")]
    )
    rec_late = validator.validate(raw_late).validated_record
    status_late = buffer.add(rec_late)
    assert status_late.is_late is True


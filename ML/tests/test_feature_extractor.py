from datetime import datetime, timezone, timedelta
import pytest
import numpy as np
from ML.models.telemetry import (
    ValidatedTelemetryRecord,
    ValidatedSensorReading,
    OperatingContext,
    ReadingQuality,
)
from ML.models.features import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION
from ML.shared.history_buffer import HistoryBuffer
from ML.detector_b.feature_extractor import FeatureExtractor


def build_telemetry(t, temp, curr, vib, press, output, rpm=1500.0, load=75.0, state="running", mode="standard"):
    return ValidatedTelemetryRecord(
        machine_id="motor_001",
        device_id="esp32_01",
        window_id=f"win-{int(t.timestamp())}",
        measured_at=t,
        window_start=t - timedelta(seconds=3),
        window_end=t,
        operating_context=OperatingContext(operating_state=state, operating_mode=mode, rpm=rpm, load_percentage=load),
        readings=[
            ValidatedSensorReading(sensor_id="s_temp", parameter="motor_temperature", value_original=temp, unit_original="degC", value_normalized=temp, unit_normalized="degC"),
            ValidatedSensorReading(sensor_id="s_curr", parameter="mean_current", value_original=curr, unit_original="A", value_normalized=curr, unit_normalized="A"),
            ValidatedSensorReading(sensor_id="s_vib", parameter="vibration_rms", value_original=vib, unit_original="mm/s", value_normalized=vib, unit_normalized="mm/s"),
            ValidatedSensorReading(sensor_id="s_press", parameter="mean_pressure", value_original=press, unit_original="kPa", value_normalized=press, unit_normalized="kPa"),
            ValidatedSensorReading(sensor_id="s_out", parameter="mean_output", value_original=output, unit_original="kW", value_normalized=output, unit_normalized="kW"),
        ]
    )


def test_feature_extractor_column_order_and_types():
    extractor = FeatureExtractor()
    buffer = HistoryBuffer()
    t0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Ingest 25 records (75 seconds of history)
    records = []
    for i in range(25):
        t = t0 + timedelta(seconds=3 * i)
        rec = build_telemetry(t, temp=50.0 + i * 0.2, curr=10.0 + (i % 2), vib=2.0, press=100.0 + i, output=15.0)
        buffer.add(rec)
        records.append(rec)

    current_rec = records[-1]
    snapshot = extractor.extract(current_rec, buffer)

    assert snapshot.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert len(snapshot.features) == len(FEATURE_COLUMNS)
    assert set(snapshot.features.keys()) == set(FEATURE_COLUMNS)

    # Check numpy vector
    vec = snapshot.to_ordered_vector()
    assert len(vec) == 22
    assert isinstance(vec, list)
    np_arr = np.array(vec)
    assert np_arr.shape == (22,)
    assert not np.isnan(np_arr).any()


def test_feature_extractor_calculations():
    extractor = FeatureExtractor()
    buffer = HistoryBuffer()
    t0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Feed history where temp rises from 50.0 to 55.0 over 15s (5 steps of 3s)
    # i=0: t0, temp=50
    # i=1: t0+3, temp=51
    # i=2: t0+6, temp=52
    # i=3: t0+9, temp=53
    # i=4: t0+12, temp=54
    # i=5: t0+15, temp=55
    for i in range(6):
        t = t0 + timedelta(seconds=3 * i)
        rec = build_telemetry(t, temp=50.0 + i, curr=12.0, vib=1.5, press=100.0 + (i * 2.0), output=20.0)
        buffer.add(rec)

    current_rec = build_telemetry(t0 + timedelta(seconds=15), temp=55.0, curr=12.0, vib=1.5, press=110.0, output=20.0)
    snapshot = extractor.extract(current_rec, buffer)

    # Direct features
    assert snapshot.features["mean_temperature"] == 55.0
    assert snapshot.features["mean_current"] == 12.0
    assert snapshot.features["vibration_rms"] == 1.5
    assert snapshot.features["mean_pressure"] == 110.0
    assert snapshot.features["mean_output"] == 20.0

    # 15s temp change: temp now (55) - temp 15s ago (50) = 5.0
    assert pytest.approx(snapshot.features["temperature_change_15s"], 0.1) == 5.0

    # Operating context
    assert snapshot.features["rpm"] == 1500.0
    assert snapshot.features["load_percentage"] == 75.0
    assert snapshot.features["operating_state_code"] == 2  # "running" -> 2
    assert snapshot.features["operating_mode_code"] == 1   # "standard" -> 1
    assert snapshot.features["has_rpm"] == 1.0
    assert snapshot.features["has_load"] == 1.0


def test_feature_extractor_missing_context_imputation():
    """Missing RPM/load must be imputed cleanly with has_rpm=0 and has_load=0."""
    extractor = FeatureExtractor()
    buffer = HistoryBuffer()
    t0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Context without RPM or load
    rec = ValidatedTelemetryRecord(
        machine_id="motor_001",
        device_id="esp32_01",
        window_id="win-no-rpm",
        measured_at=t0,
        window_start=t0 - timedelta(seconds=3),
        window_end=t0,
        operating_context=OperatingContext(operating_state="idle"),  # no rpm, no load
        readings=[
            ValidatedSensorReading(sensor_id="s1", parameter="motor_temperature", value_original=45.0, unit_original="degC", value_normalized=45.0, unit_normalized="degC")
        ]
    )
    buffer.add(rec)

    snapshot = extractor.extract(rec, buffer)
    assert snapshot.features["rpm"] == 0.0
    assert snapshot.features["load_percentage"] == 0.0
    assert snapshot.features["has_rpm"] == 0.0
    assert snapshot.features["has_load"] == 0.0
    assert snapshot.features["operating_state_code"] == 0  # idle


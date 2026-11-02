from datetime import datetime, timezone, timedelta
import pytest
from ML.models.telemetry import (
    ValidatedTelemetryRecord,
    ValidatedSensorReading,
    OperatingContext,
    ReadingQuality,
)
from ML.models.results import DetectorType, EvaluationStatus
from ML.shared.history_buffer import HistoryBuffer
from ML.detector_a.statistical_engine import StatisticalEngine, StatisticalRuleConfig
from ML.detector_a.engine import DetectorA


def create_record(timestamp, temp_val, curr_val, win_id="w-1"):
    return ValidatedTelemetryRecord(
        machine_id="motor_001",
        device_id="esp32_01",
        window_id=win_id,
        measured_at=timestamp,
        window_start=timestamp - timedelta(seconds=3),
        window_end=timestamp,
        operating_context=OperatingContext(operating_state="running", rpm=1500.0),
        readings=[
            ValidatedSensorReading(
                sensor_id="temp_01",
                parameter="motor_temperature",
                value_original=temp_val,
                unit_original="degC",
                value_normalized=temp_val,
                unit_normalized="degC",
                quality=ReadingQuality.valid,
            ),
            ValidatedSensorReading(
                sensor_id="curr_01",
                parameter="mean_current",
                value_original=curr_val,
                unit_original="A",
                value_normalized=curr_val,
                unit_normalized="A",
                quality=ReadingQuality.valid,
            ),
        ]
    )


def test_statistical_engine_insufficient_history():
    """Engine must return insufficient_data when buffer lacks minimum required observations."""
    buffer = HistoryBuffer()
    engine = StatisticalEngine()
    
    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    rec = create_record(t0, 50.0, 10.0, win_id="w-0")
    buffer.add(rec)

    # Only 1 sample in history, 15s window requires min 3 samples
    result = engine.evaluate(rec, buffer)
    assert result.status == EvaluationStatus.insufficient_data
    assert len(result.findings) == 0


def test_statistical_engine_rolling_metrics_and_zscore():
    buffer = HistoryBuffer()
    engine = StatisticalEngine()
    
    # Configure statistical rule: z_score > 3.0 on motor_temperature
    rule = StatisticalRuleConfig(
        rule_id="stat-temp-zscore",
        parameter="motor_temperature",
        reference_mean=50.0,
        reference_std=2.0,
        z_score_threshold=3.0,
        persistence_count=1,  # immediate for this test
    )
    engine.add_rule(rule)

    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    # Feed 5 records (15 seconds) with normal temperatures: 50.0
    for i in range(5):
        t = t0 + timedelta(seconds=3 * i)
        rec = create_record(t, 50.0 + (i * 0.1), 10.0, win_id=f"w-{i}")
        buffer.add(rec)

    # 6th record with temperature spike 60.0 (z-score = (60.0 - 50.0) / 2.0 = 5.0 > 3.0)
    t_spike = t0 + timedelta(seconds=15)
    rec_spike = create_record(t_spike, 60.0, 10.0, win_id="w-spike")
    buffer.add(rec_spike)

    result = engine.evaluate(rec_spike, buffer)
    assert result.status == EvaluationStatus.completed
    assert result.detector == DetectorType.statistical
    assert len(result.findings) >= 1
    
    z_finding = next((f for f in result.findings if f.rule_id == "stat-temp-zscore"), None)
    assert z_finding is not None
    assert z_finding.observed_value == 60.0
    assert z_finding.details["z_score"] == 5.0


def test_zero_variance_protection():
    """Engine must not divide by zero when reference_std is zero or near zero."""
    buffer = HistoryBuffer()
    engine = StatisticalEngine()
    
    rule = StatisticalRuleConfig(
        rule_id="stat-temp-zero-std",
        parameter="motor_temperature",
        reference_mean=50.0,
        reference_std=0.0,  # Zero variance!
        z_score_threshold=2.0,
    )
    engine.add_rule(rule)

    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        t = t0 + timedelta(seconds=3 * i)
        rec = create_record(t, 50.0, 10.0, win_id=f"w-{i}")
        buffer.add(rec)

    rec_last = create_record(t0 + timedelta(seconds=15), 52.0, 10.0, win_id="w-last")
    buffer.add(rec_last)

    result = engine.evaluate(rec_last, buffer)
    assert result.status == EvaluationStatus.completed
    # Should not raise ZeroDivisionError and should include a warning
    assert any("near-zero" in str(w).lower() or "variance" in str(w).lower() for w in result.data_quality.warnings)


def test_persistence_condition():
    """Rule with persistence_count = 3 must only produce a finding on the 3rd consecutive violation."""
    buffer = HistoryBuffer()
    engine = StatisticalEngine()
    
    rule = StatisticalRuleConfig(
        rule_id="stat-persist-rule",
        parameter="motor_temperature",
        rate_of_change_threshold=5.0,  # > 5 °C/min
        persistence_count=3,
    )
    engine.add_rule(rule)

    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    # Establish base 15s history
    for i in range(5):
        t = t0 + timedelta(seconds=3 * i)
        rec = create_record(t, 50.0, 10.0, win_id=f"w-init-{i}")
        buffer.add(rec)

    # Violation 1: temp jump to 55.0 (+5 deg in 15s = 20 °C/min > 5.0)
    t1 = t0 + timedelta(seconds=15)
    r1 = create_record(t1, 55.0, 10.0, win_id="w-v1")
    buffer.add(r1)
    res1 = engine.evaluate(r1, buffer)
    assert len(res1.findings) == 0  # Persistence 1/3, no alert yet

    # Violation 2: temp jump to 60.0
    t2 = t0 + timedelta(seconds=18)
    r2 = create_record(t2, 60.0, 10.0, win_id="w-v2")
    buffer.add(r2)
    res2 = engine.evaluate(r2, buffer)
    assert len(res2.findings) == 0  # Persistence 2/3, no alert yet

    # Violation 3: temp jump to 65.0
    t3 = t0 + timedelta(seconds=21)
    r3 = create_record(t3, 65.0, 10.0, win_id="w-v3")
    buffer.add(r3)
    res3 = engine.evaluate(r3, buffer)
    assert len(res3.findings) == 1  # Persistence 3/3 satisfied!
    assert res3.findings[0].rule_id == "stat-persist-rule"


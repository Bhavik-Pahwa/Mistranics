from datetime import datetime, timezone, timedelta
import pytest
import numpy as np
from ML.models.detector_b_schemas import DetectorBStatus, PHYSICAL_FEATURE_COLUMNS, SIMULATOR_FEATURE_COLUMNS
from ML.detector_b.features_physical import PhysicalFeatureExtractor, PhysicalTelemetryPoint
from ML.detector_b.features_simulator import SimulatorFeatureExtractor, SimulatorTelemetryPoint


def test_physical_features_warmup_insufficient_data():
    extractor = PhysicalFeatureExtractor()
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    
    # Only 10 seconds of telemetry (not yet 60s warm-up)
    points = [
        PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=3 * i), temperature=45.0 + i)
        for i in range(4)
    ]
    vec, status, err = extractor.extract(points, current_time=t0 + timedelta(seconds=9))
    assert status == DetectorBStatus.INSUFFICIENT_DATA
    assert vec is None
    assert "Warm-up incomplete" in err


def test_physical_features_60s_complete():
    extractor = PhysicalFeatureExtractor()
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    
    # 25 points at 3s intervals = 75 seconds of data (covers 60s window)
    points = [
        PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=3 * i), temperature=50.0 + (i * 0.5))
        for i in range(25)
    ]
    t_eval = t0 + timedelta(seconds=3 * 24)
    vec, status, err = extractor.extract(points, current_time=t_eval)
    assert status == DetectorBStatus.NORMAL
    assert err is None
    assert len(vec) == 12
    assert isinstance(vec, list)
    
    # Check 3s window features: covers readings at t_eval-3s (61.5) and t_eval (62.0)
    # mean_3s = 61.75, max_3s = 62.0, min_3s = 61.5, std_3s = 0.25
    assert vec[0] == pytest.approx(61.75, 0.01)
    assert vec[1] == pytest.approx(62.0, 0.01)
    assert vec[2] == pytest.approx(61.5, 0.01)
    assert vec[3] == pytest.approx(0.25, 0.01)


def test_physical_features_sensor_error():
    extractor = PhysicalFeatureExtractor()
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    
    points = [
        PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=3 * i), temperature=50.0)
        for i in range(24)
    ]
    # Add an out-of-range sensor reading (> 125 degC or None)
    points.append(PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=72), temperature=180.0))
    
    vec, status, err = extractor.extract(points, current_time=t0 + timedelta(seconds=72))
    assert status == DetectorBStatus.SENSOR_ERROR
    assert vec is None


def test_simulator_features_complete_36_columns():
    extractor = SimulatorFeatureExtractor()
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    
    # 25 points across 75s
    points = [
        SimulatorTelemetryPoint(
            timestamp=t0 + timedelta(seconds=3 * i),
            temperature=50.0 + (i * 0.2),
            vibration=1.5 + (i * 0.05),
            current=12.0 + (i * 0.1),
        )
        for i in range(25)
    ]
    t_eval = t0 + timedelta(seconds=72)
    vec, status, err = extractor.extract(points, current_time=t_eval)
    assert status == DetectorBStatus.NORMAL
    assert err is None
    assert len(vec) == 36
    assert isinstance(vec, list)


def test_simulator_features_missing_sensor_error():
    """Missing vibration or current must produce SENSOR_ERROR."""
    extractor = SimulatorFeatureExtractor()
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    
    points = [
        SimulatorTelemetryPoint(
            timestamp=t0 + timedelta(seconds=3 * i),
            temperature=50.0,
            vibration=1.5,
            current=12.0,
        )
        for i in range(24)
    ]
    # Missing vibration on current window
    points.append(SimulatorTelemetryPoint(
        timestamp=t0 + timedelta(seconds=72),
        temperature=55.0,
        vibration=None,
        current=12.0,
    ))
    vec, status, err = extractor.extract(points, current_time=t0 + timedelta(seconds=72))
    assert status == DetectorBStatus.SENSOR_ERROR
    assert vec is None
    assert "Missing vibration" in err

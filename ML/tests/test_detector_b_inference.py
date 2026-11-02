from datetime import datetime, timezone, timedelta
import numpy as np
import pytest
from ML.models.features import FeatureSnapshot, FEATURE_SCHEMA_VERSION, FEATURE_COLUMNS
from ML.models.telemetry import ReadingQuality, ValidatedTelemetryRecord, ValidatedSensorReading, OperatingContext
from ML.models.results import DetectorType, EvaluationStatus
from ML.detector_b.trainer import IsolationForestTrainer
from ML.detector_b.inference import IsolationForestInference
from ML.detector_b.engine import DetectorB
from ML.shared.history_buffer import HistoryBuffer


@pytest.fixture
def trained_model():
    rng = np.random.default_rng(100)
    # Generate 100 samples of normal operations
    X_train = []
    for _ in range(100):
        row = [50.0 + rng.normal(0, 0.5) for _ in range(len(FEATURE_COLUMNS))]
        X_train.append(row)
    trainer = IsolationForestTrainer(model_version="test-model-1.0")
    return trainer.train(np.array(X_train), val_ratio=0.2)


def test_inference_model_unavailable():
    infer = IsolationForestInference(model_package=None)
    now = datetime.now(timezone.utc)
    snapshot = FeatureSnapshot(
        snapshot_id="s-1",
        machine_id="motor_001",
        feature_timestamp=now,
        source_window_start=now,
        source_window_end=now,
        features={col: 50.0 for col in FEATURE_COLUMNS},
    )
    result = infer.score(snapshot)
    assert result.status == EvaluationStatus.model_unavailable
    assert len(result.findings) == 0


def test_inference_normal_vs_anomaly(trained_model):
    infer = IsolationForestInference(model_package=trained_model)
    now = datetime.now(timezone.utc)

    # 1. Score normal features (close to training mean 50.0)
    normal_snapshot = FeatureSnapshot(
        snapshot_id="s-normal",
        machine_id="motor_001",
        feature_timestamp=now,
        source_window_start=now,
        source_window_end=now,
        features={col: 50.0 for col in FEATURE_COLUMNS},
    )
    normal_res = infer.score(normal_snapshot)
    assert normal_res.status == EvaluationStatus.completed
    assert normal_res.detector == DetectorType.isolation_forest
    assert len(normal_res.findings) == 0
    assert normal_res.metrics["is_anomaly"] is False

    # 2. Score extreme anomaly features (out-of-distribution values)
    anomaly_snapshot = FeatureSnapshot(
        snapshot_id="s-anomaly",
        machine_id="motor_001",
        feature_timestamp=now,
        source_window_start=now,
        source_window_end=now,
        features={col: 1000.0 for col in FEATURE_COLUMNS},
    )
    anomaly_res = infer.score(anomaly_snapshot)
    assert anomaly_res.status == EvaluationStatus.completed
    assert len(anomaly_res.findings) == 1
    assert anomaly_res.metrics["is_anomaly"] is True
    assert anomaly_res.findings[0].rule_id == "isolation_forest_anomaly"


def test_detector_b_end_to_end_evaluation(trained_model):
    detector_b = DetectorB(model_package=trained_model)
    buffer = HistoryBuffer()
    t0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Ingest 5 normal telemetry records into buffer
    for i in range(5):
        t = t0 + timedelta(seconds=3 * i)
        rec = ValidatedTelemetryRecord(
            machine_id="motor_001",
            device_id="esp32_01",
            window_id=f"win-{i}",
            measured_at=t,
            window_start=t - timedelta(seconds=3),
            window_end=t,
            operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
            readings=[
                ValidatedSensorReading(sensor_id="temp", parameter="motor_temperature", value_original=50.0, unit_original="degC", value_normalized=50.0, unit_normalized="degC"),
                ValidatedSensorReading(sensor_id="curr", parameter="mean_current", value_original=12.0, unit_original="A", value_normalized=12.0, unit_normalized="A"),
                ValidatedSensorReading(sensor_id="vib", parameter="vibration_rms", value_original=1.8, unit_original="mm/s", value_normalized=1.8, unit_normalized="mm/s"),
                ValidatedSensorReading(sensor_id="press", parameter="mean_pressure", value_original=102.0, unit_original="kPa", value_normalized=102.0, unit_normalized="kPa"),
                ValidatedSensorReading(sensor_id="out", parameter="mean_output", value_original=22.0, unit_original="kW", value_normalized=22.0, unit_normalized="kW"),
            ]
        )
        buffer.add(rec)

    # Evaluate latest record
    result = detector_b.evaluate(rec, buffer)
    assert result.status == EvaluationStatus.completed
    assert result.model_version == "test-model-1.0"
    assert result.feature_schema_version == FEATURE_SCHEMA_VERSION


import os
import shutil
import tempfile
import numpy as np
import pytest
from ML.models.features import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION
from ML.detector_b.trainer import IsolationForestTrainer, TrainedModelPackage, load_model_package


def generate_synthetic_healthy_features(n_samples=200):
    """Generate representative synthetic normal machine telemetry feature rows."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n_samples):
        # Normal machine operating around steady state
        row = [
            55.0 + rng.normal(0, 1.0),      # mean_temperature
            54.0 + rng.normal(0, 1.0),      # min_temperature
            56.0 + rng.normal(0, 1.0),      # max_temperature
            12.0 + rng.normal(0, 0.5),      # mean_current
            1.8 + rng.normal(0, 0.1),       # vibration_rms
            2.5 + rng.normal(0, 0.2),       # peak_rms
            2.6 + rng.normal(0, 0.2),       # peak_vibration
            102.0 + rng.normal(0, 2.0),     # mean_pressure
            22.0 + rng.normal(0, 0.5),      # mean_output
            rng.normal(0, 0.2),             # temperature_change_15s
            rng.normal(0, 0.4),             # temperature_change_60s
            1.8 + rng.normal(0, 0.05),      # rolling_vibration_average_15s
            1.8 + rng.normal(0, 0.05),      # rolling_vibration_average_60s
            0.5 + rng.normal(0, 0.05),      # rolling_current_std_15s
            0.5 + rng.normal(0, 0.05),      # rolling_current_std_60s
            rng.normal(0, 0.1),             # pressure_rate_of_change
            1500.0 + rng.normal(0, 5.0),    # rpm
            80.0 + rng.normal(0, 2.0),      # load_percentage
            1.0,                            # operating_mode_code (standard)
            2.0,                            # operating_state_code (running)
            1.0,                            # has_rpm
            1.0,                            # has_load
        ]
        rows.append(row)
    return np.array(rows)


def test_trainer_fit_and_threshold_selection():
    X = generate_synthetic_healthy_features(n_samples=200)
    trainer = IsolationForestTrainer(model_version="iso-v1.0")
    pkg = trainer.train(X, val_ratio=0.2, contamination=0.05)

    assert pkg.metadata.model_version == "iso-v1.0"
    assert pkg.metadata.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert pkg.metadata.feature_columns == FEATURE_COLUMNS
    assert pkg.metadata.decision_threshold is not None
    assert pkg.estimator is not None


def test_trainer_persistence_and_loading():
    X = generate_synthetic_healthy_features(n_samples=150)
    trainer = IsolationForestTrainer(model_version="iso-persist-test")
    pkg = trainer.train(X, val_ratio=0.2)

    tmp_dir = tempfile.mkdtemp()
    try:
        model_path = os.path.join(tmp_dir, "model.joblib")
        pkg.save(model_path)

        assert os.path.exists(model_path)
        meta_path = os.path.join(tmp_dir, "model.json")
        assert os.path.exists(meta_path)

        # Load back
        loaded = load_model_package(model_path)
        assert loaded.metadata.model_version == "iso-persist-test"
        assert loaded.metadata.decision_threshold == pkg.metadata.decision_threshold

        # Score a normal sample
        normal_sample = X[0:1]
        score_orig = pkg.estimator.score_samples(normal_sample)[0]
        score_loaded = loaded.estimator.score_samples(normal_sample)[0]
        assert pytest.approx(score_orig, 1e-5) == score_loaded

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


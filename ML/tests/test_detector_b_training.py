import os
import tempfile
import shutil
import pytest
from ML.detector_b.data_physical import generate_physical_dataset, partition_dataset
from ML.detector_b.data_simulator import generate_simulator_dataset
from ML.detector_b.train_physical import PhysicalModelTrainer
from ML.detector_b.train_simulator import SimulatorModelTrainer
from ML.models.detector_b_schemas import PHYSICAL_FEATURE_COLUMNS, SIMULATOR_FEATURE_COLUMNS
from ML.detector_b.trainer import load_model_package


def test_train_physical_model():
    dataset = generate_physical_dataset(n_steps=120)
    splits = partition_dataset(dataset, train_ratio=0.55, val_ratio=0.25, gap_samples=10)

    trainer = PhysicalModelTrainer(model_version="phys-v2.0")
    pkg = trainer.train(splits["train_X"], splits["val_X"], splits["val_labels"])

    assert pkg.metadata.model_version == "phys-v2.0"
    assert pkg.metadata.feature_columns == PHYSICAL_FEATURE_COLUMNS
    assert len(pkg.metadata.feature_columns) == 12
    assert pkg.metadata.decision_threshold is not None
    assert pkg.estimator.n_estimators == 200

    tmp_dir = tempfile.mkdtemp()
    try:
        model_path = os.path.join(tmp_dir, "physical_model.joblib")
        pkg.save(model_path)
        assert os.path.exists(model_path)
        assert os.path.exists(os.path.join(tmp_dir, "physical_model.json"))

        loaded = load_model_package(model_path)
        assert loaded.metadata.model_version == "phys-v2.0"
        assert loaded.metadata.decision_threshold == pkg.metadata.decision_threshold
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_train_simulator_model():
    dataset = generate_simulator_dataset(n_steps=150)
    splits = partition_dataset(dataset, train_ratio=0.55, val_ratio=0.25, gap_samples=10)

    trainer = SimulatorModelTrainer(model_version="sim-v2.0")
    pkg = trainer.train(splits["train_X"], splits["val_X"], splits["val_labels"])

    assert pkg.metadata.model_version == "sim-v2.0"
    assert pkg.metadata.feature_columns == SIMULATOR_FEATURE_COLUMNS
    assert len(pkg.metadata.feature_columns) == 36
    assert pkg.metadata.decision_threshold is not None
    assert pkg.estimator.n_estimators == 200

    tmp_dir = tempfile.mkdtemp()
    try:
        model_path = os.path.join(tmp_dir, "simulator_model.joblib")
        pkg.save(model_path)
        assert os.path.exists(model_path)
        assert os.path.exists(os.path.join(tmp_dir, "simulator_model.json"))

        loaded = load_model_package(model_path)
        assert loaded.metadata.model_version == "sim-v2.0"
        assert loaded.metadata.decision_threshold == pkg.metadata.decision_threshold
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


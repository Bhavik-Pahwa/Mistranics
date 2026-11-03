import pytest
import numpy as np
from ML.detector_b.data_physical import generate_physical_dataset, partition_dataset
from ML.detector_b.data_simulator import generate_simulator_dataset
from ML.models.detector_b_schemas import PHYSICAL_FEATURE_COLUMNS, SIMULATOR_FEATURE_COLUMNS


def test_physical_dataset_generation_and_partitioning():
    dataset = generate_physical_dataset(n_steps=120)  # 360 seconds of simulated physical run
    assert len(dataset.features) > 0
    assert dataset.features.shape[1] == len(PHYSICAL_FEATURE_COLUMNS)
    assert len(dataset.labels) == len(dataset.features)
    assert set(dataset.labels).issuperset({"normal", "abnormal"})

    # Partition chronologically with 60s temporal gap
    splits = partition_dataset(dataset, train_ratio=0.6, val_ratio=0.2, gap_samples=20)
    assert len(splits["train_X"]) > 0
    assert len(splits["val_X"]) > 0
    assert len(splits["test_X"]) > 0

    # Training set must be strictly normal per PRD Section 6.5
    assert all(label == "normal" for label in splits["train_labels"])

    # Validation and test sets include abnormal recordings for threshold calibration
    assert "abnormal" in splits["val_labels"]
    assert "abnormal" in splits["test_labels"]


def test_simulator_dataset_generation_and_partitioning():
    dataset = generate_simulator_dataset(n_steps=150)
    assert len(dataset.features) > 0
    assert dataset.features.shape[1] == len(SIMULATOR_FEATURE_COLUMNS)
    assert len(dataset.labels) == len(dataset.features)
    assert set(dataset.labels).issuperset({"normal", "heat", "imb", "brg"})

    splits = partition_dataset(dataset, train_ratio=0.6, val_ratio=0.2, gap_samples=20)
    assert len(splits["train_X"]) > 0
    assert len(splits["val_X"]) > 0
    assert len(splits["test_X"]) > 0

    # Training set is normal motor operation across loads
    assert all(label == "normal" for label in splits["train_labels"])
    assert any(label != "normal" for label in splits["val_labels"])


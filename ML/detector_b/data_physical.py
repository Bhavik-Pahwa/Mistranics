import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from pydantic import BaseModel

from ML.models.detector_b_schemas import PHYSICAL_FEATURE_COLUMNS, DetectorBStatus
from ML.detector_b.features_physical import PhysicalFeatureExtractor, PhysicalTelemetryPoint


class DatasetContainer:
    def __init__(self, features: np.ndarray, labels: List[str], timestamps: List[datetime], metadata: Dict[str, Any]):
        self.features = features
        self.labels = labels
        self.timestamps = timestamps
        self.metadata = metadata


def generate_physical_dataset(n_steps: int = 200, seed: int = 42) -> DatasetContainer:
    """
    Generates synthetic physical DS18B20 temperature telemetry covering:
    1. Normal motor steady-state operation and variations (42 - 54°C).
    2. Deliberately induced abnormal overheating (80 - 95°C).
    3. Cooling down / transition phases.
    Extracts 12 rolling statistical features per 3-second step.
    """
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 11, 3, 8, 0, 0, tzinfo=timezone.utc)
    
    # 1. Generate sequence of temperature readings
    raw_points: List[PhysicalTelemetryPoint] = []
    labels_raw: List[str] = []

    current_temp = 35.0

    for step in range(n_steps):
        t = t0 + timedelta(seconds=3 * step)
        
        # Scenario breakdown
        if step < int(n_steps * 0.50):
            # Phase 1: Normal steady-state operation (target 48°C)
            target = 48.0 + rng.normal(0, 1.2)
            current_temp += (target - current_temp) * 0.1
            label = "normal"
        elif step < int(n_steps * 0.70):
            # Phase 2: First overheating event (for validation partition)
            target = 88.0 + rng.normal(0, 2.0)
            current_temp += (target - current_temp) * 0.15
            label = "abnormal"
        elif step < int(n_steps * 0.82):
            # Phase 3: Intermediate recovery
            target = 46.0
            current_temp += (target - current_temp) * 0.1
            label = "normal"
        else:
            # Phase 4: Second overheating event (for test partition)
            target = 90.0 + rng.normal(0, 2.0)
            current_temp += (target - current_temp) * 0.15
            label = "abnormal"

        temp_noisy = float(round(current_temp + rng.normal(0, 0.2), 2))
        raw_points.append(PhysicalTelemetryPoint(timestamp=t, temperature=temp_noisy, status="valid"))
        labels_raw.append(label)

    # 2. Extract 12-feature rows using PhysicalFeatureExtractor
    extractor = PhysicalFeatureExtractor(min_history_seconds=55.0, min_history_samples=18)
    features_list: List[List[float]] = []
    final_labels: List[str] = []
    final_timestamps: List[datetime] = []

    for i in range(len(raw_points)):
        history_slice = raw_points[:i+1]
        vec, status, _ = extractor.extract(history_slice, current_time=raw_points[i].timestamp)
        if status == DetectorBStatus.NORMAL and vec is not None:
            features_list.append(vec)
            final_labels.append(labels_raw[i])
            final_timestamps.append(raw_points[i].timestamp)

    features_arr = np.array(features_list, dtype=float)
    return DatasetContainer(
        features=features_arr,
        labels=final_labels,
        timestamps=final_timestamps,
        metadata={"feature_columns": list(PHYSICAL_FEATURE_COLUMNS), "data_source": "physical"},
    )


def partition_dataset(
    dataset: DatasetContainer,
    train_ratio: float = 0.50,
    val_ratio: float = 0.25,
    gap_samples: int = 10,
) -> Dict[str, Any]:
    """
    Chronological partition with temporal gap to eliminate rolling-window leakage across splits.
    Train split contains exclusively normal samples per PRD Section 6.5 & 7.5.
    Validation and Test sets contain both normal and abnormal recordings for threshold calibration.
    """
    X = dataset.features
    y = dataset.labels
    n = len(X)

    # Bound gap so it cannot consume all available data
    actual_gap = max(1, min(gap_samples, int(n * 0.05)))
    net_samples = n - (2 * actual_gap)
    if net_samples < 3:
        actual_gap = 1
        net_samples = max(3, n - 2)

    train_len = max(1, int(net_samples * train_ratio))
    val_len = max(1, int(net_samples * val_ratio))
    test_len = max(1, net_samples - train_len - val_len)

    # 1. Train partition
    train_end = train_len
    train_X = X[:train_end]
    train_y = y[:train_end]
    pure_normal_mask = [label == "normal" for label in train_y]
    train_X = train_X[pure_normal_mask]
    train_y = [lbl for lbl in train_y if lbl == "normal"]

    # 2. Validation partition after gap
    val_start = train_end + actual_gap
    val_end = val_start + val_len
    val_X = X[val_start:val_end]
    val_y = y[val_start:val_end]

    # 3. Test partition after second gap
    test_start = val_end + actual_gap
    test_X = X[test_start:]
    test_y = y[test_start:]

    return {
        "train_X": train_X,
        "train_labels": train_y,
        "val_X": val_X,
        "val_labels": val_y,
        "test_X": test_X,
        "test_labels": test_y,
    }

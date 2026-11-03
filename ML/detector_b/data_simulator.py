import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from ML.models.detector_b_schemas import SIMULATOR_FEATURE_COLUMNS, DetectorBStatus
from ML.detector_b.features_simulator import SimulatorFeatureExtractor, SimulatorTelemetryPoint
from ML.detector_b.data_physical import DatasetContainer


def generate_simulator_dataset(n_steps: int = 250, seed: int = 42) -> DatasetContainer:
    """
    Generates synthetic online motor simulator telemetry covering:
    1. Normal operating conditions across variable speeds and loads (0-100%).
    2. Overheating condition ('heat').
    3. Severe mechanical imbalance ('imb').
    4. Bearing friction and impulses ('brg').
    Extracts 36 rolling statistical features per 3-second step.
    """
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 11, 3, 8, 0, 0, tzinfo=timezone.utc)

    raw_points: List[SimulatorTelemetryPoint] = []
    labels_raw: List[str] = []

    temp = 32.0
    vib = 1.2
    curr = 11.0

    for step in range(n_steps):
        t = t0 + timedelta(seconds=3 * step)

        if step < int(n_steps * 0.55):
            # Normal motor operation across loads (rpm ~ 1500-1800, load ~ 60-80%)
            t_target = 42.0 + rng.normal(0, 1.0)
            v_target = 1.3 + rng.normal(0, 0.1)
            c_target = 11.5 + rng.normal(0, 0.3)
            label = "normal"
        elif step < int(n_steps * 0.70):
            # Overheating fault ('heat')
            t_target = 82.0 + rng.normal(0, 2.0)
            v_target = 1.5 + rng.normal(0, 0.15)
            c_target = 13.0 + rng.normal(0, 0.5)
            label = "heat"
        elif step < int(n_steps * 0.85):
            # Mechanical imbalance ('imb') - high vibration
            t_target = 54.0 + rng.normal(0, 1.0)
            v_target = 5.2 + rng.normal(0, 0.4)
            c_target = 14.5 + rng.normal(0, 0.6)
            label = "imb"
        else:
            # Bearing damage ('brg') - impulse vibrations and heating
            t_target = 68.0 + rng.normal(0, 1.5)
            v_target = 4.8 + rng.normal(0, 0.5)
            c_target = 18.0 + rng.normal(0, 0.8)
            label = "brg"

        temp += (t_target - temp) * 0.15
        vib += (v_target - vib) * 0.25
        curr += (c_target - curr) * 0.25

        raw_points.append(
            SimulatorTelemetryPoint(
                timestamp=t,
                temperature=float(round(temp + rng.normal(0, 0.1), 2)),
                vibration=float(round(max(0.1, vib + rng.normal(0, 0.05)), 3)),
                current=float(round(max(0.5, curr + rng.normal(0, 0.1)), 2)),
                status="valid",
            )
        )
        labels_raw.append(label)

    # Extract 36-feature rows using SimulatorFeatureExtractor
    extractor = SimulatorFeatureExtractor(min_history_seconds=55.0, min_history_samples=18)
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
        metadata={"feature_columns": list(SIMULATOR_FEATURE_COLUMNS), "data_source": "simulator"},
    )


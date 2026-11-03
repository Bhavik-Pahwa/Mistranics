import math
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Sequence
import numpy as np
from pydantic import BaseModel

from ML.models.detector_b_schemas import (
    SIMULATOR_FEATURE_COLUMNS,
    DetectorBStatus,
)


class SimulatorTelemetryPoint(BaseModel):
    timestamp: datetime
    temperature: Optional[float] = None
    vibration: Optional[float] = None
    current: Optional[float] = None
    status: str = "valid"

    def is_valid(self) -> Tuple[bool, Optional[str]]:
        if self.status != "valid":
            return False, f"Sensor status is '{self.status}'"
        if self.temperature is None or not math.isfinite(self.temperature):
            return False, "Missing temperature reading"
        if self.vibration is None or not math.isfinite(self.vibration):
            return False, "Missing vibration reading"
        if self.current is None or not math.isfinite(self.current):
            return False, "Missing current reading"
        if self.vibration < 0.0 or self.current < 0.0:
            return False, "Negative vibration or current reading"
        return True, None


class SimulatorFeatureExtractor:
    """
    Model 2 Feature Pipeline: Extracts 36 statistical features across Temperature,
    Vibration, and Current from the online motor simulator over 3s, 15s, and 60s windows.
    """

    def __init__(self, min_history_seconds: float = 55.0, min_history_samples: int = 15):
        self.min_history_seconds = min_history_seconds
        self.min_history_samples = min_history_samples

    def extract(
        self,
        history: Sequence[SimulatorTelemetryPoint],
        current_time: Optional[datetime] = None,
    ) -> Tuple[Optional[List[float]], DetectorBStatus, Optional[str]]:
        if not history:
            return None, DetectorBStatus.INSUFFICIENT_DATA, "History is empty"

        eval_time = current_time or history[-1].timestamp
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # 1. Check validity of latest telemetry point in current 3s window
        latest_point = history[-1]
        valid, reason = latest_point.is_valid()
        if not valid:
            return None, DetectorBStatus.SENSOR_ERROR, f"Sensor error on latest telemetry: {reason}"

        # 2. Filter history within 60s window [eval_time - 60s, eval_time]
        cutoff_60s = eval_time - timedelta(seconds=60)
        window_60s_points = [p for p in history if cutoff_60s <= p.timestamp <= eval_time]

        # 3. Warm-up verification
        if not window_60s_points:
            return None, DetectorBStatus.INSUFFICIENT_DATA, "Warm-up incomplete: no points in 60s window"

        history_span = (eval_time - window_60s_points[0].timestamp).total_seconds()
        if history_span < self.min_history_seconds or len(window_60s_points) < self.min_history_samples:
            return (
                None,
                DetectorBStatus.INSUFFICIENT_DATA,
                f"Warm-up incomplete: history span is {history_span:.1f}s ({len(window_60s_points)} samples), "
                f"requires >= 60s ({self.min_history_samples} samples)",
            )

        # Verify all sensors valid in historical window
        for p in window_60s_points:
            p_valid, p_reason = p.is_valid()
            if not p_valid:
                return None, DetectorBStatus.SENSOR_ERROR, f"Historical sensor error: {p_reason}"

        # 4. Extract windows: 3s, 15s, 60s
        cutoff_15s = eval_time - timedelta(seconds=15)
        cutoff_3s = eval_time - timedelta(seconds=3)

        points_3s = [p for p in window_60s_points if cutoff_3s <= p.timestamp <= eval_time]
        points_15s = [p for p in window_60s_points if cutoff_15s <= p.timestamp <= eval_time]
        points_60s = window_60s_points

        if not points_3s:
            points_3s = [latest_point]

        def _stats(arr: List[float]) -> Tuple[float, float, float, float]:
            if not arr:
                return 0.0, 0.0, 0.0, 0.0
            return (
                float(np.mean(arr)),
                float(np.max(arr)),
                float(np.min(arr)),
                float(np.std(arr)) if len(arr) > 1 else 0.0,
            )

        # Extract features for each window
        features: List[float] = []

        for pts in (points_3s, points_15s, points_60s):
            t_vals = [p.temperature for p in pts if p.temperature is not None]
            v_vals = [p.vibration for p in pts if p.vibration is not None]
            c_vals = [p.current for p in pts if p.current is not None]

            features.extend(_stats(t_vals))
            features.extend(_stats(v_vals))
            features.extend(_stats(c_vals))

        if len(features) != len(SIMULATOR_FEATURE_COLUMNS):
            return (
                None,
                DetectorBStatus.MODEL_ERROR,
                f"Feature extraction dimension mismatch: got {len(features)}, expected {len(SIMULATOR_FEATURE_COLUMNS)}",
            )

        return features, DetectorBStatus.NORMAL, None


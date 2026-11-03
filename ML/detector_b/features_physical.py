from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Sequence
import numpy as np
from pydantic import BaseModel, Field

from ML.models.detector_b_schemas import (
    PHYSICAL_FEATURE_COLUMNS,
    DetectorBStatus,
)


class PhysicalTelemetryPoint(BaseModel):
    timestamp: datetime
    temperature: Optional[float] = None
    status: str = "valid"

    def is_valid(self) -> bool:
        if self.status != "valid" or self.temperature is None:
            return False
        # DS18B20 physical sensor measurement range: -55°C to +125°C
        return -55.0 <= self.temperature <= 125.0


class PhysicalFeatureExtractor:
    """
    Model 1 Feature Pipeline: Extracts 12 statistical features from physical DS18B20 temperature
    across 3-second, 15-second, and 60-second rolling windows.
    """

    def __init__(self, min_history_seconds: float = 55.0, min_history_samples: int = 15):
        self.min_history_seconds = min_history_seconds
        self.min_history_samples = min_history_samples

    def extract(
        self,
        history: Sequence[PhysicalTelemetryPoint],
        current_time: Optional[datetime] = None,
    ) -> Tuple[Optional[List[float]], DetectorBStatus, Optional[str]]:
        if not history:
            return None, DetectorBStatus.INSUFFICIENT_DATA, "History is empty"

        eval_time = current_time or history[-1].timestamp
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # 1. Check validity of latest telemetry point in current 3s window
        latest_point = history[-1]
        if not latest_point.is_valid():
            return (
                None,
                DetectorBStatus.SENSOR_ERROR,
                f"Invalid or out-of-range physical temperature reading: {latest_point.temperature}",
            )

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

        # Check for sensor errors across the 60s window
        for p in window_60s_points:
            if not p.is_valid():
                return (
                    None,
                    DetectorBStatus.SENSOR_ERROR,
                    f"Corrupt or invalid sensor reading in historical window: {p.temperature}",
                )

        # 4. Extract features for 3s, 15s, and 60s windows
        cutoff_15s = eval_time - timedelta(seconds=15)
        cutoff_3s = eval_time - timedelta(seconds=3)

        points_3s = [p for p in window_60s_points if cutoff_3s <= p.timestamp <= eval_time]
        points_15s = [p for p in window_60s_points if cutoff_15s <= p.timestamp <= eval_time]
        points_60s = window_60s_points

        # Fallback for 3s window if boundaries land on single sample
        if not points_3s:
            points_3s = [latest_point]

        vals_3s = [p.temperature for p in points_3s if p.temperature is not None]
        vals_15s = [p.temperature for p in points_15s if p.temperature is not None]
        vals_60s = [p.temperature for p in points_60s if p.temperature is not None]

        features: List[float] = [
            # 3s window
            float(np.mean(vals_3s)),
            float(np.max(vals_3s)),
            float(np.min(vals_3s)),
            float(np.std(vals_3s)) if len(vals_3s) > 1 else 0.0,
            # 15s window
            float(np.mean(vals_15s)),
            float(np.max(vals_15s)),
            float(np.min(vals_15s)),
            float(np.std(vals_15s)) if len(vals_15s) > 1 else 0.0,
            # 60s window
            float(np.mean(vals_60s)),
            float(np.max(vals_60s)),
            float(np.min(vals_60s)),
            float(np.std(vals_60s)) if len(vals_60s) > 1 else 0.0,
        ]

        return features, DetectorBStatus.NORMAL, None


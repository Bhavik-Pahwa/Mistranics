from datetime import datetime
from typing import List, Dict
from pydantic import BaseModel, Field
from ML.models.telemetry import ReadingQuality

FEATURE_SCHEMA_VERSION = "features-1.0"

FEATURE_COLUMNS = [
    "mean_temperature",
    "min_temperature",
    "max_temperature",
    "mean_current",
    "vibration_rms",
    "peak_rms",
    "peak_vibration",
    "mean_pressure",
    "mean_output",
    "temperature_change_15s",
    "temperature_change_60s",
    "rolling_vibration_average_15s",
    "rolling_vibration_average_60s",
    "rolling_current_std_15s",
    "rolling_current_std_60s",
    "pressure_rate_of_change",
    "rpm",
    "load_percentage",
    "operating_mode_code",
    "operating_state_code",
    "has_rpm",
    "has_load",
]

OPERATING_MODE_MAP = {
    "unknown": 0,
    "standard": 1,
    "eco": 2,
    "high_performance": 3,
    "maintenance": 4,
}

OPERATING_STATE_MAP = {
    "unknown": -1,
    "idle": 0,
    "starting": 1,
    "running": 2,
    "stopping": 3,
    "fault": 4,
}


class FeatureSnapshot(BaseModel):
    snapshot_id: str
    machine_id: str
    feature_timestamp: datetime
    source_window_start: datetime
    source_window_end: datetime
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    features: Dict[str, float]
    quality_status: ReadingQuality = ReadingQuality.valid
    missing_features: List[str] = Field(default_factory=list)
    insufficient_history: List[str] = Field(default_factory=list)

    def to_ordered_vector(self) -> List[float]:
        """Return features in the exact fixed schema column order."""
        return [float(self.features.get(col, 0.0)) for col in FEATURE_COLUMNS]


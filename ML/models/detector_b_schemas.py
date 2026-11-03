from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, model_validator


class DetectorBStatus(str, Enum):
    NORMAL = "NORMAL"
    ANOMALY = "ANOMALY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SENSOR_ERROR = "SENSOR_ERROR"
    MODEL_ERROR = "MODEL_ERROR"


class ModelType(str, Enum):
    physical = "physical"
    simulator = "simulator"


class DataSource(str, Enum):
    physical = "physical"
    simulator = "simulator"
    simulation = "simulation"


# Model 1 (Physical Hardware DS18B20): 12 features
# 4 statistics (mean, max, min, std) x 3 windows (3s, 15s, 60s)
PHYSICAL_FEATURE_COLUMNS: List[str] = [
    # 3-second window
    "temp_mean_3s",
    "temp_max_3s",
    "temp_min_3s",
    "temp_std_3s",
    # 15-second window
    "temp_mean_15s",
    "temp_max_15s",
    "temp_min_15s",
    "temp_std_15s",
    # 60-second window
    "temp_mean_60s",
    "temp_max_60s",
    "temp_min_60s",
    "temp_std_60s",
]

# Model 2 (Online Motor Simulator): 36 features
# 3 sensors (temp, vib, curr) x 4 statistics (mean, max, min, std) x 3 windows (3s, 15s, 60s)
SIMULATOR_FEATURE_COLUMNS: List[str] = [
    # 3-second window
    "temp_mean_3s",
    "temp_max_3s",
    "temp_min_3s",
    "temp_std_3s",
    "vib_mean_3s",
    "vib_max_3s",
    "vib_min_3s",
    "vib_std_3s",
    "curr_mean_3s",
    "curr_max_3s",
    "curr_min_3s",
    "curr_std_3s",
    # 15-second window
    "temp_mean_15s",
    "temp_max_15s",
    "temp_min_15s",
    "temp_std_15s",
    "vib_mean_15s",
    "vib_max_15s",
    "vib_min_15s",
    "vib_std_15s",
    "curr_mean_15s",
    "curr_max_15s",
    "curr_min_15s",
    "curr_std_15s",
    # 60-second window
    "temp_mean_60s",
    "temp_max_60s",
    "temp_min_60s",
    "temp_std_60s",
    "vib_mean_60s",
    "vib_max_60s",
    "vib_min_60s",
    "vib_std_60s",
    "curr_mean_60s",
    "curr_max_60s",
    "curr_min_60s",
    "curr_std_60s",
]


class DetectorBResult(BaseModel):
    """
    Common Output Contract for Detector B (Version 2.0).
    Conforms to PRD Section 9.3 common response structure.
    """
    model_config = ConfigDict(extra="allow")

    detector: str = "B"
    model_type: ModelType
    model_version: str
    timestamp: datetime
    anomaly_score: Optional[float] = None
    decision_threshold: Optional[float] = None
    status: DetectorBStatus
    data_source: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_utc(self):
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        return self


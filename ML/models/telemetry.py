from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ReadingQuality(str, Enum):
    valid = "valid"
    missing = "missing"
    out_of_range = "out_of_range"
    suspect = "suspect"


class SensorReading(BaseModel):
    sensor_id: str
    parameter: str
    value: Optional[float] = Field(default=None, strict=True, allow_inf_nan=False)
    unit: str
    quality: ReadingQuality = ReadingQuality.valid

    @model_validator(mode="after")
    def validate_missing_value_consistency(self):
        if self.value is None and self.quality == ReadingQuality.valid:
            self.quality = ReadingQuality.missing
        return self


class OperatingContext(BaseModel):
    operating_state: Optional[str] = None  # e.g., "idle", "starting", "running", "stopping"
    operating_mode: Optional[str] = None   # e.g., "standard", "eco", "high_performance"
    rpm: Optional[float] = None
    load_percentage: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class RawTelemetryPayload(BaseModel):
    schema_version: str = "1.0"
    machine_id: str
    device_id: str
    reading_id: str
    measured_at: datetime
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    received_at: Optional[datetime] = None
    operating_context: OperatingContext = Field(default_factory=OperatingContext)
    readings: List[SensorReading] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_utc_and_windows(self):
        # Normalize timestamps to UTC
        if self.measured_at.tzinfo is None:
            self.measured_at = self.measured_at.replace(tzinfo=timezone.utc)
        else:
            self.measured_at = self.measured_at.astimezone(timezone.utc)

        if self.received_at:
            if self.received_at.tzinfo is None:
                self.received_at = self.received_at.replace(tzinfo=timezone.utc)
            else:
                self.received_at = self.received_at.astimezone(timezone.utc)

        # Default 3-second window [measured_at - 3s, measured_at]
        if self.window_start is None and self.window_end is None:
            self.window_end = self.measured_at
            self.window_start = self.measured_at - timedelta(seconds=3)
        else:
            if self.window_start and self.window_start.tzinfo is None:
                self.window_start = self.window_start.replace(tzinfo=timezone.utc)
            elif self.window_start:
                self.window_start = self.window_start.astimezone(timezone.utc)

            if self.window_end and self.window_end.tzinfo is None:
                self.window_end = self.window_end.replace(tzinfo=timezone.utc)
            elif self.window_end:
                self.window_end = self.window_end.astimezone(timezone.utc)
        return self


class ValidatedSensorReading(BaseModel):
    sensor_id: str
    parameter: str
    value_original: Optional[float] = None
    unit_original: str
    value_normalized: Optional[float] = Field(default=None, strict=True, allow_inf_nan=False)
    unit_normalized: Optional[str] = None
    quality: ReadingQuality = ReadingQuality.valid


class ValidatedTelemetryRecord(BaseModel):
    schema_version: str = "1.0"
    machine_id: str
    device_id: str
    window_id: str
    measured_at: datetime
    window_start: datetime
    window_end: datetime
    received_at: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operating_context: OperatingContext = Field(default_factory=OperatingContext)
    readings: List[ValidatedSensorReading] = Field(default_factory=list)
    quality_status: ReadingQuality = ReadingQuality.valid
    quality_warnings: List[str] = Field(default_factory=list)

    def get_reading(self, parameter: str) -> Optional[ValidatedSensorReading]:
        """Find the first reading for a parameter."""
        for r in self.readings:
            if r.parameter == parameter:
                return r
        return None

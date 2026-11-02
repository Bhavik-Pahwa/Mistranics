import math
from datetime import timezone, timedelta
from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    AwareDatetime,
    AfterValidator,
    model_validator,
)

Time = Annotated[AwareDatetime, AfterValidator(lambda v: v.astimezone(timezone.utc))]
Identity = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^\S+$")]
Quality = Literal["valid", "missing", "out_of_range", "suspect"]
Detector = Literal["manufacturer_limits", "statistical", "isolation_forest"]


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite JSON value")
    if isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    if isinstance(value, list):
        for item in value:
            finite_json(item)
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def finite(cls, value):
        return finite_json(value)


class Measurement(Strict):
    sensor_id: Identity
    parameter: Identity
    value: float | None = Field(strict=True)
    unit: Identity
    quality: Quality = "valid"

    @model_validator(mode="after")
    def missing(self):
        if (self.value is None) != (self.quality == "missing"):
            raise ValueError(
                "null values require missing quality; missing quality requires null"
            )
        return self


class Telemetry(Strict):
    schema_version: Literal["1.0"]
    machine_id: Identity
    device_id: Identity
    reading_id: Identity
    window_start: Time | None = None
    window_end: Time | None = None
    measured_at: Time
    received_at: Time | None = None
    operating_context: dict = Field(default_factory=dict)
    readings: list[Measurement] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def window(self):
        if self.window_start is None and self.window_end is None:
            self.window_end = self.measured_at
            self.window_start = self.measured_at - timedelta(seconds=3)
        if (
            self.window_start is None
            or self.window_end is None
            or self.window_start >= self.window_end
        ):
            raise ValueError("both boundaries required, start before end")
        if not self.window_start <= self.measured_at <= self.window_end:
            raise ValueError("measured_at must fall within window")
        keys = [(r.sensor_id, r.parameter) for r in self.readings]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate sensor/parameter")
        return self


class DataQuality(Strict):
    status: Quality
    warnings: list[str] = Field(default_factory=list, max_length=500)


class DetectorResult(Strict):
    schema_version: Literal["1.0"]
    detector: Detector
    machine_id: Identity
    window_id: Identity
    run_id: Identity
    evaluated_at: Time
    status: Literal[
        "completed",
        "insufficient_data",
        "invalid_input",
        "model_unavailable",
        "processing_error",
    ]
    findings: list[dict] = Field(default_factory=list, max_length=500)
    data_quality: DataQuality
    model_or_config_version: Identity
    model_version: Identity | None = None
    feature_schema_version: Identity | None = None
    config_version: Identity | None = None
    source_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def versions(self):
        if self.detector == "isolation_forest" and not (
            self.model_version and self.feature_schema_version
        ):
            raise ValueError(
                "Detector B requires model_version and feature_schema_version"
            )
        if self.detector != "isolation_forest" and not self.config_version:
            raise ValueError("Detector A requires config_version")
        return self


class Action(Strict):
    reason: str = Field(min_length=1, max_length=2000)


class Rule(Strict):
    id: Identity
    detector: Detector
    match: dict
    outcome: Literal["anomaly", "indeterminate"]


class Policy(Strict):
    version: Identity
    approved_by: Identity
    required_detectors: list[Detector] = Field(min_length=1)
    timeout_seconds: int = Field(gt=0)
    rules: list[Rule]
    alerts_enabled: bool = False
    manual_resolution: bool = False
    resolve_on_normal: bool = False
    severity: str | None = None

    @model_validator(mode="after")
    def unique_detectors(self):
        if len(set(self.required_detectors)) != len(self.required_detectors):
            raise ValueError("duplicate required detectors")
        if any(r.detector not in self.required_detectors for r in self.rules):
            raise ValueError("rules must refer to required detectors")
        return self

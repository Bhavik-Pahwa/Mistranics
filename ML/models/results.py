from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ML.models.telemetry import ReadingQuality


class DetectorType(str, Enum):
    manufacturer_limits = "manufacturer_limits"
    statistical = "statistical"
    isolation_forest = "isolation_forest"


class EvaluationStatus(str, Enum):
    completed = "completed"
    insufficient_data = "insufficient_data"
    invalid_input = "invalid_input"
    model_unavailable = "model_unavailable"
    processing_error = "processing_error"


class FindingKind(str, Enum):
    machine_condition = "machine_condition"
    data_quality = "data_quality"


class Finding(BaseModel):
    finding_id: str
    rule_id: str
    parameter: Optional[str] = None
    sensor_id: Optional[str] = None
    kind: FindingKind = FindingKind.machine_condition
    observed_value: Optional[float] = None
    threshold: Optional[float] = None
    direction: Optional[str] = None  # e.g., "upper", "lower", "excess", "deviation"
    unit: Optional[str] = None
    limit_category: Optional[str] = None  # e.g., "warning", "protective_trip", "statistical_deviation"
    evidence_time: Optional[datetime] = None
    source_reference: Optional[Dict[str, Any]] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class DataQualityMetadata(BaseModel):
    status: ReadingQuality = ReadingQuality.valid
    warnings: List[str] = Field(default_factory=list)


class DetectorResultEnvelope(BaseModel):
    schema_version: str = "1.0"
    detector: DetectorType
    machine_id: str
    window_id: str
    run_id: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EvaluationStatus
    findings: List[Finding] = Field(default_factory=list)
    data_quality: DataQualityMetadata = Field(default_factory=DataQualityMetadata)
    model_or_config_version: str
    model_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    config_version: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    skipped_reasons: List[str] = Field(default_factory=list)


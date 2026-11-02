from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class LimitVerificationStatus(str, Enum):
    candidate = "candidate"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"


class LimitCategory(str, Enum):
    operating_range = "operating_range"
    warning = "warning"
    protective_trip = "protective_trip"


class TimeBasis(str, Enum):
    instantaneous = "instantaneous"
    averaged = "averaged"
    duration_based = "duration_based"


class SourceReference(BaseModel):
    document: str
    revision: Optional[str] = None
    page_or_section: Optional[str] = None
    candidate_id: Optional[str] = None
    extraction_method: Optional[str] = "manual"  # e.g., "manual", "llm_extracted"


class ManufacturerLimitRecord(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    limit_id: str
    machine_id: str
    machine_model: Optional[str] = None
    sensor_id: Optional[str] = None
    parameter: str
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    unit: str
    category: LimitCategory = LimitCategory.warning
    applicable_state: Optional[str] = None
    applicable_mode: Optional[str] = None
    min_rpm: Optional[float] = None
    max_rpm: Optional[float] = None
    min_load: Optional[float] = None
    max_load: Optional[float] = None
    time_basis: TimeBasis = TimeBasis.instantaneous
    duration_seconds: Optional[float] = None
    source: SourceReference
    status: LimitVerificationStatus = LimitVerificationStatus.candidate
    reviewer: Optional[str] = None
    approved_at: Optional[datetime] = None
    config_version: str = "limits-1.0"

    def is_applicable(
        self,
        state: Optional[str] = None,
        mode: Optional[str] = None,
        rpm: Optional[float] = None,
        load: Optional[float] = None,
    ) -> bool:
        """Check if operating context satisfies the limit's applicability preconditions."""
        if self.applicable_state and (
            state is None or self.applicable_state.lower() != state.lower()
        ):
            return False
        if self.applicable_mode and (
            mode is None or self.applicable_mode.lower() != mode.lower()
        ):
            return False
        if self.min_rpm is not None and (rpm is None or rpm < self.min_rpm):
            return False
        if self.max_rpm is not None and (rpm is None or rpm > self.max_rpm):
            return False
        if self.min_load is not None and (load is None or load < self.min_load):
            return False
        if self.max_load is not None and (load is None or load > self.max_load):
            return False
        return True

from typing import Literal
from pydantic import Field, model_validator
from backend.app.schemas import Strict, Identity


class StartSession(Strict):
    machine_id: Identity
    incident_id: Identity | None = None
    document_id: Identity | None = None
    document_version: Identity | None = None

    @model_validator(mode="after")
    def version(self):
        if bool(self.document_id) != bool(self.document_version):
            raise ValueError("Select both document_id and document_version")
        return self


class Ask(Strict):
    request_id: Identity
    text: str = Field(min_length=1, max_length=8000)


class Report(Strict):
    kind: Literal[
        "step_completed",
        "step_not_completed",
        "issue_persists",
        "improved",
        "observation",
        "maintenance",
    ]
    step_id: Identity | None = None
    text: str = Field(min_length=1, max_length=4000)


class Citation(Strict):
    chunk_id: Identity
    document_id: Identity
    version: Identity
    page: int = Field(ge=1)


class Hypothesis(Strict):
    cause: str = Field(min_length=1, max_length=1500)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=20)
    contradicting_evidence: list[str] = Field(default_factory=list, max_length=20)
    confidence: Literal["LOW", "MEDIUM"] = "LOW"


class Instruction(Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    source: Citation
    source_quote: str = Field(min_length=1, max_length=3000)
    requires_technician: bool = True
    kind: Literal["diagnostic_check", "corrective_action"] = "diagnostic_check"


class Answer(Strict):
    response_type: Literal["TROUBLESHOOTING", "INSUFFICIENT_EVIDENCE"]
    condition_summary: str = Field(max_length=3000)
    possible_causes: list[Hypothesis] = Field(default_factory=list, max_length=10)
    instructions: list[Instruction] = Field(default_factory=list, max_length=15)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    safety_warnings: list[str] = Field(default_factory=list, max_length=20)
    sources: list[Citation] = Field(default_factory=list, max_length=30)

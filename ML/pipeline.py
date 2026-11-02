import json
import logging
from typing import Union, Dict, Any, List, Optional
from pydantic import BaseModel

from ML.models.telemetry import RawTelemetryPayload, ReadingQuality
from ML.models.results import (
    DetectorResultEnvelope,
    EvaluationStatus,
    DetectorType,
    DataQualityMetadata,
)
from ML.shared.validator import TelemetryValidator, ValidationResult
from ML.shared.history_buffer import HistoryBuffer, BufferIngestStatus
from ML.detector_a.engine import DetectorA
from ML.detector_b.engine import DetectorB
from ML.detector_b.trainer import TrainedModelPackage


class PipelineOutput(BaseModel):
    validation_status: ValidationResult
    buffer_status: Optional[BufferIngestStatus] = None
    limits_result: Optional[DetectorResultEnvelope] = None
    statistical_result: Optional[DetectorResultEnvelope] = None
    isolation_forest_result: Optional[DetectorResultEnvelope] = None

    @property
    def all_detector_results(self) -> List[DetectorResultEnvelope]:
        results = []
        if self.limits_result:
            results.append(self.limits_result)
        if self.statistical_result:
            results.append(self.statistical_result)
        if self.isolation_forest_result:
            results.append(self.isolation_forest_result)
        return results


class MachineHealthPipeline:
    """
    End-to-end Machine Health Engine orchestrator:
    1. Validates and normalizes 3-second telemetry windows.
    2. Updates time-ordered history buffer (15s & 60s context).
    3. Executes Detector A (Manufacturer Limits & Statistical Rules).
    4. Executes Detector B (Feature Extraction & Isolation Forest Inference).
    5. Returns structured results conforming to the unified detector contract.
    """

    def __init__(
        self,
        model_package: Optional[TrainedModelPackage] = None,
        late_threshold_seconds: float = 15.0,
    ):
        self.validator = TelemetryValidator()
        self.history_buffer = HistoryBuffer(
            late_threshold_seconds=late_threshold_seconds
        )
        self.detector_a = DetectorA()
        self.detector_b = DetectorB(model_package=model_package)

    def process(
        self, payload: Union[RawTelemetryPayload, Dict[str, Any], str]
    ) -> PipelineOutput:
        # 1. Parse into RawTelemetryPayload if necessary
        if isinstance(payload, str):
            payload_dict = json.loads(payload)
            raw = RawTelemetryPayload.model_validate(payload_dict)
        elif isinstance(payload, dict):
            raw = RawTelemetryPayload.model_validate(payload)
        else:
            raw = payload

        # 2. Shared Data Validation & Unit Normalization
        val_result = self.validator.validate(raw)
        if not val_result.is_valid:
            # Emit invalid_input envelopes for downstream traceability
            err_envelope = DetectorResultEnvelope(
                detector=DetectorType.manufacturer_limits,
                machine_id=raw.machine_id or "unknown",
                window_id=raw.reading_id or "unknown",
                run_id="err-val",
                status=EvaluationStatus.invalid_input,
                data_quality=DataQualityMetadata(
                    status=ReadingQuality.suspect, warnings=val_result.errors
                ),
                model_or_config_version="none",
                skipped_reasons=val_result.errors,
            )
            return PipelineOutput(
                validation_status=val_result,
                limits_result=err_envelope,
                statistical_result=err_envelope.model_copy(
                    update={"detector": DetectorType.statistical}
                ),
                isolation_forest_result=err_envelope.model_copy(
                    update={"detector": DetectorType.isolation_forest}
                ),
            )

        validated_record = val_result.validated_record

        # 3. Add to chronological history buffer (with deduplication & late arrival check)
        buf_status = self.history_buffer.add(validated_record)
        if buf_status.is_duplicate:
            # A duplicate is not a new successful normal evaluation.
            return PipelineOutput(
                validation_status=val_result, buffer_status=buf_status
            )

        return self.evaluate_record(
            validated_record, self.history_buffer, val_result, buf_status
        )

    def evaluate_record(self, record, history, validation=None, buffer_status=None):
        """Evaluate a canonical backend record without revalidating/converting telemetry."""
        validation = validation or ValidationResult(
            is_valid=True, validated_record=record
        )
        results = {}
        calls = {
            "limits_result": (
                DetectorType.manufacturer_limits,
                lambda: self.detector_a.evaluate_limits(record),
            ),
            "statistical_result": (
                DetectorType.statistical,
                lambda: self.detector_a.evaluate_statistical(record, history),
            ),
            "isolation_forest_result": (
                DetectorType.isolation_forest,
                lambda: self.detector_b.evaluate(record, history),
            ),
        }
        for key, (detector, call) in calls.items():
            try:
                results[key] = call()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Detector failed machine=%s window=%s detector=%s",
                    record.machine_id,
                    record.window_id,
                    detector.value,
                )
                results[key] = DetectorResultEnvelope(
                    detector=detector,
                    machine_id=record.machine_id,
                    window_id=record.window_id,
                    run_id=f"failed-{detector.value}-{record.window_id}",
                    status=EvaluationStatus.processing_error,
                    data_quality=DataQualityMetadata(status=ReadingQuality.suspect),
                    model_or_config_version="unavailable",
                    skipped_reasons=["Detector evaluation failed"],
                )
        return PipelineOutput(
            validation_status=validation, buffer_status=buffer_status, **results
        )

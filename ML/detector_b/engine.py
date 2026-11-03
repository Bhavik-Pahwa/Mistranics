import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, Sequence, Any
from ML.models.telemetry import ValidatedTelemetryRecord, ReadingQuality
from ML.models.results import (
    DetectorResultEnvelope,
    EvaluationStatus,
    DetectorType,
    Finding,
    FindingKind,
    DataQualityMetadata,
)
from ML.models.detector_b_schemas import (
    DetectorBResult,
    DetectorBStatus,
    ModelType,
)
from ML.shared.history_buffer import HistoryBuffer
from ML.detector_b.feature_extractor import FeatureExtractor
from ML.detector_b.inference import IsolationForestInference
from ML.detector_b.trainer import TrainedModelPackage
from ML.detector_b.features_physical import PhysicalTelemetryPoint
from ML.detector_b.features_simulator import SimulatorTelemetryPoint
from ML.detector_b.dual_engine import DualIsolationForestEngine


class DetectorB:
    """
    Detector B Engine (Version 2.0): Dual Isolation Forest Anomaly Detector.
    Supports both Model 1 (Physical Hardware DS18B20) and Model 2 (Online Simulator),
    while preserving backward compatibility with single-model evaluation pipelines.
    """

    def __init__(
        self,
        model_package: Optional[TrainedModelPackage] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        physical_package: Optional[TrainedModelPackage] = None,
        simulator_package: Optional[TrainedModelPackage] = None,
    ):
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.inference = IsolationForestInference(model_package=model_package)
        self.dual_engine = DualIsolationForestEngine(
            physical_package=physical_package,
            simulator_package=simulator_package,
        )

    def load_model(self, filepath: str) -> None:
        """Loads legacy model or auto-detects schema."""
        self.inference.load_model(filepath)

    def load_physical_model(self, filepath: str) -> None:
        self.dual_engine.load_physical_model(filepath)

    def load_simulator_model(self, filepath: str) -> None:
        self.dual_engine.load_simulator_model(filepath)

    def evaluate_dual(
        self,
        history: Sequence[Any],
        source: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> DetectorBResult:
        """Evaluates using PRD v2.0 Dual Isolation Forest Engine."""
        return self.dual_engine.evaluate(history, source=source, current_time=current_time)

    def evaluate(
        self,
        record: ValidatedTelemetryRecord,
        history_buffer: HistoryBuffer,
        run_id: Optional[str] = None,
    ) -> DetectorResultEnvelope:
        eval_run_id = run_id or f"run-iso-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. Dual Isolation Forest Path (PRD v2.0)
        # -------------------------------------------------------------
        has_dual = (
            self.dual_engine.physical_inference.model_package is not None
            or self.dual_engine.simulator_inference.model_package is not None
        )

        if has_dual:
            ctx = record.operating_context
            source = None
            if hasattr(ctx, "source"):
                source = getattr(ctx, "source")
            elif hasattr(ctx, "extra") and isinstance(ctx.extra, dict):
                source = ctx.extra.get("source")

            # Fetch chronological historical records from buffer (60s context)
            history_records = history_buffer.get_recent_history(
                record.machine_id, seconds=65.0, as_of=record.measured_at
            )
            if not history_records or history_records[-1].window_id != record.window_id:
                history_records = list(history_records) + [record]

            # Determine whether physical or simulator telemetry
            has_vib = record.get_reading("vibration_rms") is not None or record.get_reading("vibration") is not None
            has_curr = record.get_reading("mean_current") is not None or record.get_reading("current") is not None

            is_sim = (source in ("simulator", "simulation")) or (has_vib and has_curr)

            if is_sim:
                # Build SimulatorTelemetryPoints
                sim_points: list[SimulatorTelemetryPoint] = []
                for rec in history_records:
                    t_val = rec.get_reading("motor_temperature") or rec.get_reading("temperature")
                    v_val = rec.get_reading("vibration_rms") or rec.get_reading("vibration")
                    c_val = rec.get_reading("mean_current") or rec.get_reading("current")
                    sim_points.append(
                        SimulatorTelemetryPoint(
                            timestamp=rec.measured_at,
                            temperature=t_val.value_normalized if t_val else None,
                            vibration=v_val.value_normalized if v_val else None,
                            current=c_val.value_normalized if c_val else None,
                            status="valid" if (t_val and v_val and c_val) else "error",
                        )
                    )
                dual_res = self.dual_engine.evaluate_simulator(sim_points, current_time=record.measured_at)
            else:
                # Build PhysicalTelemetryPoints
                phys_points: list[PhysicalTelemetryPoint] = []
                for rec in history_records:
                    t_val = rec.get_reading("temperature") or rec.get_reading("motor_temperature")
                    phys_points.append(
                        PhysicalTelemetryPoint(
                            timestamp=rec.measured_at,
                            temperature=t_val.value_normalized if t_val else None,
                            status="valid" if (t_val and t_val.quality == ReadingQuality.valid) else "error",
                        )
                    )
                dual_res = self.dual_engine.evaluate_physical(phys_points, current_time=record.measured_at)

            # Map Dual result to DetectorResultEnvelope
            status_map = {
                DetectorBStatus.NORMAL: EvaluationStatus.completed,
                DetectorBStatus.ANOMALY: EvaluationStatus.completed,
                DetectorBStatus.INSUFFICIENT_DATA: EvaluationStatus.insufficient_data,
                DetectorBStatus.SENSOR_ERROR: EvaluationStatus.invalid_input,
                DetectorBStatus.MODEL_ERROR: EvaluationStatus.model_unavailable,
            }
            eval_status = status_map.get(dual_res.status, EvaluationStatus.processing_error)

            findings: list[Finding] = []
            if dual_res.status == DetectorBStatus.ANOMALY:
                findings.append(
                    Finding(
                        finding_id=f"f-iso-{uuid.uuid4().hex[:8]}",
                        rule_id=f"isolation_forest_{dual_res.model_type.value}_anomaly",
                        kind=FindingKind.machine_condition,
                        observed_value=dual_res.anomaly_score,
                        threshold=dual_res.decision_threshold,
                        direction="anomaly",
                        unit="anomaly_score",
                        limit_category="ml_multivariate_outlier",
                        evidence_time=dual_res.timestamp,
                        details=dual_res.model_dump(),
                    )
                )

            envelope = DetectorResultEnvelope(
                schema_version="1.0",
                detector=DetectorType.isolation_forest,
                machine_id=record.machine_id,
                window_id=record.window_id,
                run_id=eval_run_id,
                evaluated_at=now,
                status=eval_status,
                findings=findings,
                data_quality=DataQualityMetadata(status=record.quality_status),
                model_or_config_version=dual_res.model_version,
                model_version=dual_res.model_version,
                feature_schema_version=f"{dual_res.model_type.value}-features",
                metrics={
                    "anomaly_score": dual_res.anomaly_score or 0.0,
                    "decision_threshold": dual_res.decision_threshold or 0.0,
                    "is_anomaly": dual_res.status == DetectorBStatus.ANOMALY,
                    "detector_b_v2": dual_res.model_dump(),
                },
                skipped_reasons=[dual_res.diagnostics.get("reason")] if dual_res.status in (DetectorBStatus.INSUFFICIENT_DATA, DetectorBStatus.SENSOR_ERROR, DetectorBStatus.MODEL_ERROR) and "reason" in dual_res.diagnostics else [],
            )
            # Attach dual_res directly to envelope instance for pipeline pass-through
            setattr(envelope, "_dual_result", dual_res)
            return envelope

        # -------------------------------------------------------------
        # 2. Legacy / Prototype Single Model Path
        # -------------------------------------------------------------
        snapshot = self.feature_extractor.extract(record, history_buffer)
        result = self.inference.score(snapshot, run_id=eval_run_id)
        result.window_id = record.window_id
        return result

import uuid
import math
import numpy as np
from datetime import datetime, timezone
from typing import Optional, List
from ML.models.telemetry import ReadingQuality
from ML.models.features import FeatureSnapshot, FEATURE_COLUMNS
from ML.models.results import (
    DetectorType,
    EvaluationStatus,
    DetectorResultEnvelope,
    Finding,
    FindingKind,
    DataQualityMetadata,
)
from ML.detector_b.trainer import TrainedModelPackage, load_model_package


class IsolationForestInference:
    """
    Detector B3: Real-time Isolation Forest scoring on versioned feature snapshots.
    Validates model compatibility, schema alignment, and decision thresholds.
    """

    def __init__(self, model_package: Optional[TrainedModelPackage] = None):
        self.model_package = model_package

    def load_model(self, filepath: str) -> None:
        self.model_package = load_model_package(filepath)

    def score(
        self, snapshot: FeatureSnapshot, run_id: Optional[str] = None
    ) -> DetectorResultEnvelope:
        eval_run_id = run_id or f"run-iso-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        # 1. Check if model is available
        if self.model_package is None:
            return DetectorResultEnvelope(
                schema_version="1.0",
                detector=DetectorType.isolation_forest,
                machine_id=snapshot.machine_id,
                window_id=snapshot.snapshot_id,
                run_id=eval_run_id,
                evaluated_at=now,
                status=EvaluationStatus.model_unavailable,
                findings=[],
                data_quality=DataQualityMetadata(status=snapshot.quality_status),
                model_or_config_version="none",
                skipped_reasons=["No active Isolation Forest model package is loaded"],
            )

        # 2. Check feature schema compatibility
        if (
            snapshot.feature_schema_version
            != self.model_package.metadata.feature_schema_version
        ):
            return DetectorResultEnvelope(
                schema_version="1.0",
                detector=DetectorType.isolation_forest,
                machine_id=snapshot.machine_id,
                window_id=snapshot.snapshot_id,
                run_id=eval_run_id,
                evaluated_at=now,
                status=EvaluationStatus.invalid_input,
                findings=[],
                data_quality=DataQualityMetadata(status=snapshot.quality_status),
                model_or_config_version=self.model_package.metadata.model_version,
                model_version=self.model_package.metadata.model_version,
                feature_schema_version=snapshot.feature_schema_version,
                skipped_reasons=[
                    f"Feature schema version mismatch: expected {self.model_package.metadata.feature_schema_version}, got {snapshot.feature_schema_version}"
                ],
            )

        invalid = (
            snapshot.missing_features
            or snapshot.insufficient_history
            or snapshot.quality_status != ReadingQuality.valid
            or set(snapshot.features) != set(FEATURE_COLUMNS)
            or self.model_package.metadata.feature_columns != FEATURE_COLUMNS
            or not all(math.isfinite(v) for v in snapshot.features.values())
            or not math.isfinite(self.model_package.metadata.decision_threshold)
        )
        if invalid:
            return DetectorResultEnvelope(
                detector=DetectorType.isolation_forest,
                machine_id=snapshot.machine_id,
                window_id=snapshot.snapshot_id,
                run_id=eval_run_id,
                status=EvaluationStatus.insufficient_data,
                findings=[],
                data_quality=DataQualityMetadata(status=ReadingQuality.suspect),
                model_or_config_version=self.model_package.metadata.model_version,
                model_version=self.model_package.metadata.model_version,
                feature_schema_version=snapshot.feature_schema_version,
                skipped_reasons=["Incomplete, nonfinite or incompatible feature input"],
            )

        # 3. Construct 2D vector with exact column order
        vector = snapshot.to_ordered_vector()
        X = np.array([vector], dtype=float)

        # 4. Score sample using fitted estimator
        try:
            score_val = float(self.model_package.estimator.score_samples(X)[0])
            if not math.isfinite(score_val):
                raise ValueError("Estimator returned nonfinite score")
        except Exception as e:
            return DetectorResultEnvelope(
                schema_version="1.0",
                detector=DetectorType.isolation_forest,
                machine_id=snapshot.machine_id,
                window_id=snapshot.snapshot_id,
                run_id=eval_run_id,
                evaluated_at=now,
                status=EvaluationStatus.processing_error,
                findings=[],
                data_quality=DataQualityMetadata(status=snapshot.quality_status),
                model_or_config_version=self.model_package.metadata.model_version,
                model_version=self.model_package.metadata.model_version,
                feature_schema_version=snapshot.feature_schema_version,
                skipped_reasons=[f"Scoring error: {str(e)}"],
            )

        threshold = self.model_package.metadata.decision_threshold
        is_anomaly = bool(score_val < threshold)

        findings: List[Finding] = []
        if is_anomaly:
            findings.append(
                Finding(
                    finding_id=f"f-iso-{uuid.uuid4().hex[:8]}",
                    rule_id="isolation_forest_anomaly",
                    kind=FindingKind.machine_condition,
                    observed_value=score_val,
                    threshold=threshold,
                    direction="anomaly",
                    unit="anomaly_score",
                    limit_category="ml_multivariate_outlier",
                    evidence_time=snapshot.feature_timestamp,
                    details={
                        "score_samples": score_val,
                        "decision_threshold": threshold,
                        "snapshot_id": snapshot.snapshot_id,
                        "missing_features": snapshot.missing_features,
                        "insufficient_history": snapshot.insufficient_history,
                    },
                )
            )

        return DetectorResultEnvelope(
            schema_version="1.0",
            detector=DetectorType.isolation_forest,
            machine_id=snapshot.machine_id,
            window_id=snapshot.snapshot_id,
            run_id=eval_run_id,
            evaluated_at=now,
            status=EvaluationStatus.completed,
            findings=findings,
            data_quality=DataQualityMetadata(
                status=snapshot.quality_status,
                warnings=[f"Missing features: {', '.join(snapshot.missing_features)}"]
                if snapshot.missing_features
                else [],
            ),
            model_or_config_version=self.model_package.metadata.model_version,
            model_version=self.model_package.metadata.model_version,
            feature_schema_version=self.model_package.metadata.feature_schema_version,
            metrics={
                "anomaly_score": score_val,
                "decision_threshold": threshold,
                "is_anomaly": is_anomaly,
            },
            skipped_reasons=[],
        )

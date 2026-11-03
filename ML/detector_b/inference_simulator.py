import numpy as np
from datetime import datetime, timezone
from typing import Optional, Sequence
from ML.models.detector_b_schemas import (
    DetectorBResult,
    DetectorBStatus,
    ModelType,
)
from ML.detector_b.features_simulator import (
    SimulatorFeatureExtractor,
    SimulatorTelemetryPoint,
)
from ML.detector_b.trainer import TrainedModelPackage, load_model_package


class SimulatorInference:
    """
    Model 2 Real-Time Inference: Scores simulator multivariate 36-feature vectors
    using the active simulator Isolation Forest artifact and calibrated threshold.
    """

    def __init__(self, model_package: Optional[TrainedModelPackage] = None):
        self.model_package = model_package
        self.extractor = SimulatorFeatureExtractor()

    def load_model(self, filepath: str) -> None:
        self.model_package = load_model_package(filepath, expected_schema="simulator-features-36")

    def evaluate(
        self,
        history: Sequence[SimulatorTelemetryPoint],
        current_time: Optional[datetime] = None,
    ) -> DetectorBResult:
        now = current_time or (history[-1].timestamp if history else datetime.now(timezone.utc))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if self.model_package is None:
            return DetectorBResult(
                detector="B",
                model_type=ModelType.simulator,
                model_version="unavailable",
                timestamp=now,
                anomaly_score=None,
                decision_threshold=None,
                status=DetectorBStatus.MODEL_ERROR,
                data_source="simulator",
                diagnostics={"error": "Simulator model package not loaded"},
            )

        # 1. Feature extraction & warm-up verification
        vec, status, err = self.extractor.extract(history, current_time=now)
        if status != DetectorBStatus.NORMAL or vec is None:
            return DetectorBResult(
                detector="B",
                model_type=ModelType.simulator,
                model_version=self.model_package.metadata.model_version,
                timestamp=now,
                anomaly_score=None,
                decision_threshold=self.model_package.metadata.decision_threshold,
                status=status,
                data_source="simulator",
                diagnostics={"reason": err or status.value},
            )

        # 2. Score sample using fitted estimator
        try:
            X = np.array([vec], dtype=float)
            score = float(self.model_package.estimator.score_samples(X)[0])
        except Exception as e:
            return DetectorBResult(
                detector="B",
                model_type=ModelType.simulator,
                model_version=self.model_package.metadata.model_version,
                timestamp=now,
                anomaly_score=None,
                decision_threshold=self.model_package.metadata.decision_threshold,
                status=DetectorBStatus.MODEL_ERROR,
                data_source="simulator",
                diagnostics={"error": f"Scoring error: {str(e)}"},
            )

        threshold = self.model_package.metadata.decision_threshold
        final_status = DetectorBStatus.ANOMALY if score <= threshold else DetectorBStatus.NORMAL

        return DetectorBResult(
            detector="B",
            model_type=ModelType.simulator,
            model_version=self.model_package.metadata.model_version,
            timestamp=now,
            anomaly_score=score,
            decision_threshold=threshold,
            status=final_status,
            data_source="simulator",
            diagnostics={"feature_count": len(vec)},
        )

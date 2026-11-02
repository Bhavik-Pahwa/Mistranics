from typing import Optional
from ML.models.telemetry import ValidatedTelemetryRecord
from ML.models.results import DetectorResultEnvelope
from ML.shared.history_buffer import HistoryBuffer
from ML.detector_b.feature_extractor import FeatureExtractor
from ML.detector_b.inference import IsolationForestInference
from ML.detector_b.trainer import TrainedModelPackage


class DetectorB:
    """
    Detector B Engine: Isolation Forest Multivariate Anomaly Detector.
    Integrates feature engineering (B1) with real-time model scoring (B3).
    """

    def __init__(
        self,
        model_package: Optional[TrainedModelPackage] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.inference = IsolationForestInference(model_package=model_package)

    def load_model(self, filepath: str) -> None:
        self.inference.load_model(filepath)

    def evaluate(
        self,
        record: ValidatedTelemetryRecord,
        history_buffer: HistoryBuffer,
        run_id: Optional[str] = None,
    ) -> DetectorResultEnvelope:
        # 1. Extract versioned feature snapshot
        snapshot = self.feature_extractor.extract(record, history_buffer)

        # 2. Run inference
        result = self.inference.score(snapshot, run_id=run_id)

        # Align window_id with the incoming telemetry window
        result.window_id = record.window_id
        return result


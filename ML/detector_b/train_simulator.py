import numpy as np
import sklearn
from datetime import datetime, timezone
from typing import List, Optional, Union
from sklearn.ensemble import IsolationForest

from ML.models.detector_b_schemas import SIMULATOR_FEATURE_COLUMNS
from ML.detector_b.trainer import ModelMetadata, TrainedModelPackage
from ML.detector_b.train_physical import calibrate_threshold

SIMULATOR_SCHEMA_VERSION = "simulator-features-36"


class SimulatorModelTrainer:
    """
    Model 2 Offline Training Pipeline: Fits Isolation Forest on multivariate simulator
    telemetry features (36 features) and calibrates decision threshold using validation data.
    """

    def __init__(
        self,
        model_version: str = "simulator-iso-v1.0",
        n_estimators: int = 200,
        max_samples: Union[str, int] = 256,
        contamination: Union[str, float] = "auto",
        max_features: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.model_version = model_version
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.max_features = max_features
        self.random_state = random_state
        self.n_jobs = n_jobs

    def train(
        self,
        train_X: np.ndarray,
        val_X: Optional[np.ndarray] = None,
        val_labels: Optional[List[str]] = None,
        default_percentile: float = 2.0,
    ) -> TrainedModelPackage:
        if len(train_X) < 10:
            raise ValueError(f"Insufficient training observations: {len(train_X)} (need at least 10)")

        if train_X.shape[1] != len(SIMULATOR_FEATURE_COLUMNS):
            raise ValueError(
                f"Feature dimension mismatch: expected {len(SIMULATOR_FEATURE_COLUMNS)}, got {train_X.shape[1]}"
            )

        max_samples = self.max_samples
        if isinstance(max_samples, int) and max_samples > len(train_X):
            max_samples = len(train_X)

        model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=max_samples,
            contamination=self.contamination,
            max_features=self.max_features,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
        model.fit(train_X)

        # Threshold calibration
        val_data = val_X if val_X is not None and len(val_X) > 0 else train_X
        val_scores = model.score_samples(val_data)
        threshold = calibrate_threshold(val_scores, val_labels, default_percentile)

        metadata = ModelMetadata(
            model_version=self.model_version,
            feature_schema_version=SIMULATOR_SCHEMA_VERSION,
            feature_columns=list(SIMULATOR_FEATURE_COLUMNS),
            decision_threshold=threshold,
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            training_samples=len(train_X),
            validation_samples=len(val_data),
            validation_score_min=float(np.min(val_scores)),
            validation_score_mean=float(np.mean(val_scores)),
            validation_score_std=float(np.std(val_scores)),
            created_at=datetime.now(timezone.utc),
            sklearn_version=sklearn.__version__,
        )

        return TrainedModelPackage(estimator=model, metadata=metadata)

import numpy as np
import sklearn
from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from sklearn.ensemble import IsolationForest

from ML.models.detector_b_schemas import PHYSICAL_FEATURE_COLUMNS
from ML.detector_b.trainer import ModelMetadata, TrainedModelPackage

PHYSICAL_SCHEMA_VERSION = "physical-features-12"


def calibrate_threshold(
    val_scores: np.ndarray,
    val_labels: Optional[List[str]] = None,
    default_percentile: float = 2.0,
) -> float:
    """
    Calibrates decision threshold considering precision, recall, F1-score, and false-positive rate
    on held-out validation data (PRD Section 8.3).
    """
    if val_labels is not None and len(val_labels) == len(val_scores) and any(l != "normal" for l in val_labels):
        y_true = np.array([l != "normal" for l in val_labels])
        best_f1 = -1.0
        best_threshold = float(np.percentile(val_scores, default_percentile))

        candidate_thresholds = np.linspace(float(np.min(val_scores)) - 0.02, float(np.max(val_scores)) + 0.02, 200)
        for th in candidate_thresholds:
            y_pred = val_scores <= th
            tp = int(np.sum(y_pred & y_true))
            fp = int(np.sum(y_pred & ~y_true))
            fn = int(np.sum(~y_pred & y_true))
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            fpr = fp / int(np.sum(~y_true)) if int(np.sum(~y_true)) > 0 else 0.0

            if fpr <= 0.08 and f1 > best_f1:
                best_f1 = f1
                best_threshold = float(th)

        if best_f1 > 0:
            return best_threshold

    if val_labels is not None and "normal" in val_labels:
        normal_scores = [s for s, l in zip(val_scores, val_labels) if l == "normal"]
        return float(np.percentile(normal_scores, default_percentile))

    return float(np.percentile(val_scores, default_percentile))


class PhysicalModelTrainer:
    """
    Model 1 Offline Training Pipeline: Fits Isolation Forest on physical DS18B20 temperature
    features (12 features) and calibrates decision threshold using validation data.
    """

    def __init__(
        self,
        model_version: str = "physical-iso-v1.0",
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

        if train_X.shape[1] != len(PHYSICAL_FEATURE_COLUMNS):
            raise ValueError(
                f"Feature dimension mismatch: expected {len(PHYSICAL_FEATURE_COLUMNS)}, got {train_X.shape[1]}"
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
            feature_schema_version=PHYSICAL_SCHEMA_VERSION,
            feature_columns=list(PHYSICAL_FEATURE_COLUMNS),
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

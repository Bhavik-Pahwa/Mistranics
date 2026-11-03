import os
import json
import joblib
import sklearn
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest

from ML.models.features import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION

ALLOWED_FEATURE_SCHEMAS = {FEATURE_SCHEMA_VERSION, "physical-features-12", "simulator-features-36"}


class ModelMetadata(BaseModel):
    model_version: str
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    feature_columns: List[str] = Field(default_factory=lambda: list(FEATURE_COLUMNS))
    decision_threshold: float
    contamination: Union[float, str] = "auto"
    n_estimators: int = 100
    training_samples: int = 0
    validation_samples: int = 0
    validation_score_min: float = 0.0
    validation_score_mean: float = 0.0
    validation_score_std: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sklearn_version: str = sklearn.__version__


class TrainedModelPackage:
    """
    Encapsulates a fitted Isolation Forest estimator alongside its provenance metadata.
    """

    def __init__(self, estimator: IsolationForest, metadata: ModelMetadata):
        self.estimator = estimator
        self.metadata = metadata

    def save(self, filepath: str) -> None:
        """
        Saves the Joblib model artifact and an accompanying JSON metadata file.
        If filepath ends in .joblib, metadata is written to <base>.json.
        """
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        joblib.dump(self.estimator, filepath)

        base_path, _ = os.path.splitext(filepath)
        meta_filepath = f"{base_path}.json"
        with open(meta_filepath, "w", encoding="utf-8") as f:
            f.write(self.metadata.model_dump_json(indent=2))


def load_model_package(filepath: str, expected_schema: Optional[str] = None) -> TrainedModelPackage:
    """
    Loads a trained IsolationForest estimator and its accompanying metadata.
    Validates feature schema version and columns.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Model file not found: {filepath}")

    estimator = joblib.load(filepath)

    base_path, _ = os.path.splitext(filepath)
    meta_filepath = f"{base_path}.json"
    if not os.path.exists(meta_filepath):
        raise FileNotFoundError(f"Accompanying metadata file not found: {meta_filepath}")

    with open(meta_filepath, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    metadata = ModelMetadata.model_validate(meta_data)

    target_schema = expected_schema
    if target_schema:
        if metadata.feature_schema_version != target_schema:
            raise ValueError(
                f"Model feature schema mismatch: expected {target_schema}, found {metadata.feature_schema_version}"
            )
    elif metadata.feature_schema_version not in ALLOWED_FEATURE_SCHEMAS:
        raise ValueError(
            f"Unknown model feature schema version: {metadata.feature_schema_version}"
        )

    return TrainedModelPackage(estimator=estimator, metadata=metadata)


class IsolationForestTrainer:
    """
    Detector B2: Offline training and threshold selection for Isolation Forest.
    Enforces chronological validation splitting and metadata persistence.
    """

    def __init__(
        self,
        model_version: str = "iso-v1.0",
        n_estimators: int = 100,
        max_samples: Union[str, int] = "auto",
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
        X: np.ndarray,
        val_ratio: float = 0.2,
        contamination: Optional[Union[str, float]] = None,
        threshold_percentile: float = 2.0,
    ) -> TrainedModelPackage:
        """
        Trains Isolation Forest using chronological split.
        X: 2D numpy array of shape (n_samples, n_features) matching FEATURE_COLUMNS.
        """
        if len(X) < 10:
            raise ValueError(f"Insufficient training observations: got {len(X)}, required at least 10")

        if X.shape[1] != len(FEATURE_COLUMNS):
            raise ValueError(
                f"Feature dimension mismatch: expected {len(FEATURE_COLUMNS)} columns, got {X.shape[1]}"
            )

        # Chronological train / validation split to prevent leakage
        n_val = max(1, int(len(X) * val_ratio))
        n_train = len(X) - n_val

        X_train = X[:n_train]
        X_val = X[n_train:]

        contam = contamination if contamination is not None else self.contamination

        model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=contam,
            max_features=self.max_features,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )

        model.fit(X_train)

        # Evaluate score_samples on validation set
        val_scores = model.score_samples(X_val)

        # Select decision threshold based on validation quantile (e.g. 2nd percentile of healthy data)
        threshold = float(np.percentile(val_scores, threshold_percentile))

        metadata = ModelMetadata(
            model_version=self.model_version,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_columns=list(FEATURE_COLUMNS),
            decision_threshold=threshold,
            contamination=contam,
            n_estimators=self.n_estimators,
            training_samples=len(X_train),
            validation_samples=len(X_val),
            validation_score_min=float(np.min(val_scores)),
            validation_score_mean=float(np.mean(val_scores)),
            validation_score_std=float(np.std(val_scores)),
            created_at=datetime.now(timezone.utc),
            sklearn_version=sklearn.__version__,
        )

        return TrainedModelPackage(estimator=model, metadata=metadata)

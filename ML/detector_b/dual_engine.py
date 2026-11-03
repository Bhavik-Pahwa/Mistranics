from datetime import datetime, timezone
from typing import Optional, Sequence, Any, Union
from ML.models.detector_b_schemas import (
    DetectorBResult,
    DetectorBStatus,
    ModelType,
)
from ML.detector_b.features_physical import PhysicalTelemetryPoint
from ML.detector_b.features_simulator import SimulatorTelemetryPoint
from ML.detector_b.inference_physical import PhysicalInference
from ML.detector_b.inference_simulator import SimulatorInference
from ML.detector_b.trainer import TrainedModelPackage


class DualIsolationForestEngine:
    """
    Detector B Engine (Version 2.0): Dual Isolation Forest Anomaly Detector.
    Manages two independent Isolation Forest models:
      - Model 1: Physical Hardware (DS18B20 temperature, 12 features)
      - Model 2: Online Simulator (temperature, vibration, current, 36 features)
    Routes inference based on active data source and returns the common output contract.
    """

    def __init__(
        self,
        physical_package: Optional[TrainedModelPackage] = None,
        simulator_package: Optional[TrainedModelPackage] = None,
    ):
        self.physical_inference = PhysicalInference(model_package=physical_package)
        self.simulator_inference = SimulatorInference(model_package=simulator_package)

    def load_physical_model(self, filepath: str) -> None:
        self.physical_inference.load_model(filepath)

    def load_simulator_model(self, filepath: str) -> None:
        self.simulator_inference.load_model(filepath)

    def evaluate_physical(
        self,
        history: Sequence[PhysicalTelemetryPoint],
        current_time: Optional[datetime] = None,
    ) -> DetectorBResult:
        return self.physical_inference.evaluate(history, current_time=current_time)

    def evaluate_simulator(
        self,
        history: Sequence[SimulatorTelemetryPoint],
        current_time: Optional[datetime] = None,
    ) -> DetectorBResult:
        return self.simulator_inference.evaluate(history, current_time=current_time)

    def evaluate(
        self,
        history: Sequence[Any],
        source: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> DetectorBResult:
        now = current_time or (history[-1].timestamp if history and hasattr(history[-1], "timestamp") else datetime.now(timezone.utc))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # 1. Determine active data source
        active_source = (source or "").lower().strip()

        if active_source == "physical":
            return self.evaluate_physical(history, current_time=now)
        elif active_source in ("simulator", "simulation"):
            return self.evaluate_simulator(history, current_time=now)

        # 2. Auto-detection fallback based on history items
        if history:
            first = history[0]
            if isinstance(first, SimulatorTelemetryPoint) or hasattr(first, "vibration"):
                return self.evaluate_simulator(history, current_time=now)
            elif isinstance(first, PhysicalTelemetryPoint) or hasattr(first, "temperature"):
                return self.evaluate_physical(history, current_time=now)

        return DetectorBResult(
            detector="B",
            model_type=ModelType.physical,
            model_version="unavailable",
            timestamp=now,
            anomaly_score=None,
            decision_threshold=None,
            status=DetectorBStatus.MODEL_ERROR,
            data_source=source or "unknown",
            diagnostics={"error": f"Unsupported or ambiguous data source: '{source}'"},
        )


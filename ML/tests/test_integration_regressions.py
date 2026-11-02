from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from ML.models.telemetry import SensorReading, RawTelemetryPayload
from ML.models.limits import ManufacturerLimitRecord
from ML.pipeline import MachineHealthPipeline
from ML.models.results import EvaluationStatus


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "56"])
def test_invalid_measurements_are_rejected(value):
    with pytest.raises(ValidationError):
        SensorReading(sensor_id="s", parameter="temperature", value=value, unit="degC")


def test_detector_failure_does_not_block_other_detector():
    pipeline = MachineHealthPipeline()

    def fail(record, run_id=None):
        raise RuntimeError("test failure")

    pipeline.detector_a.evaluate_limits = fail
    output = pipeline.process(
        RawTelemetryPayload(
            machine_id="m",
            device_id="d",
            reading_id="w",
            measured_at=datetime.now(timezone.utc),
            readings=[
                SensorReading(
                    sensor_id="s", parameter="temperature", value=50.0, unit="degC"
                )
            ],
        )
    )
    assert output.limits_result.status == EvaluationStatus.processing_error
    assert output.isolation_forest_result.status == EvaluationStatus.model_unavailable
    assert output.statistical_result is not None


def test_duplicate_is_not_fabricated_completed_evaluation():
    pipeline = MachineHealthPipeline()
    payload = RawTelemetryPayload(
        machine_id="m",
        device_id="d",
        reading_id="w",
        measured_at=datetime.now(timezone.utc),
    )
    pipeline.process(payload)
    assert pipeline.process(payload).all_detector_results == []


def test_missing_mode_cannot_match_conditional_limit():
    limit = ManufacturerLimitRecord(
        limit_id="mode",
        machine_id="m",
        parameter="temperature",
        unit="degC",
        source={"document": "test"},
        applicable_mode="running",
    )
    assert not limit.is_applicable()


def test_nonfinite_manufacturer_bound_is_rejected():
    with pytest.raises(ValidationError):
        ManufacturerLimitRecord(
            limit_id="bad",
            machine_id="m",
            parameter="temperature",
            unit="degC",
            upper_limit=float("nan"),
            source={"document": "test"},
        )


def test_runtime_requires_attributed_approval(tmp_path):
    import json
    from backend.app.config import Settings
    from ML.runtime import Runtime

    path = tmp_path / "limits.json"
    path.write_text(
        json.dumps(
            [
                {
                    "limit_id": "unverified",
                    "machine_id": "m",
                    "parameter": "temperature",
                    "unit": "degC",
                    "upper_limit": 75.0,
                    "status": "approved",
                    "source": {"document": "unreviewed extraction"},
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="reviewer"):
        Runtime(Settings(ml_limits_file=str(path)))

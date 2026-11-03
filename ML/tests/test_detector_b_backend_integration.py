from datetime import datetime, timezone, timedelta
import pytest
from ML.models.telemetry import RawTelemetryPayload, SensorReading, OperatingContext
from ML.models.detector_b_schemas import DetectorBStatus, ModelType
from ML.detector_b.data_physical import generate_physical_dataset, partition_dataset
from ML.detector_b.data_simulator import generate_simulator_dataset
from ML.detector_b.train_physical import PhysicalModelTrainer
from ML.detector_b.train_simulator import SimulatorModelTrainer
from ML.detector_b.dual_engine import DualIsolationForestEngine
from ML.pipeline import MachineHealthPipeline


@pytest.fixture(scope="module")
def dual_pipeline():
    # Train both models
    phys_data = generate_physical_dataset(n_steps=120)
    phys_splits = partition_dataset(phys_data, train_ratio=0.55, val_ratio=0.25, gap_samples=10)
    phys_pkg = PhysicalModelTrainer(model_version="phys-v2.0").train(
        phys_splits["train_X"], phys_splits["val_X"], phys_splits["val_labels"]
    )

    sim_data = generate_simulator_dataset(n_steps=150)
    sim_splits = partition_dataset(sim_data, train_ratio=0.55, val_ratio=0.25, gap_samples=10)
    sim_pkg = SimulatorModelTrainer(model_version="sim-v2.0").train(
        sim_splits["train_X"], sim_splits["val_X"], sim_splits["val_labels"]
    )

    pipeline = MachineHealthPipeline(
        physical_package=phys_pkg,
        simulator_package=sim_pkg,
    )
    return pipeline


def test_pipeline_physical_telemetry_stream(dual_pipeline):
    pipeline = dual_pipeline
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Warm-up steps: first 10 windows (30s) -> should report INSUFFICIENT_DATA
    for i in range(10):
        t = t0 + timedelta(seconds=3 * i)
        payload = RawTelemetryPayload(
            machine_id="physical_motor",
            device_id="esp32_serial",
            reading_id=f"win-phys-{i}",
            measured_at=t,
            operating_context=OperatingContext(source="physical"),
            readings=[
                SensorReading(sensor_id="temp_probe", parameter="temperature", value=48.0, unit="degC")
            ],
        )
        out = pipeline.process(payload)
        assert out.validation_status.is_valid is True

    assert out.detector_b_v2_result is not None
    assert out.detector_b_v2_result.status == DetectorBStatus.INSUFFICIENT_DATA

    # 2. Complete 60s warm-up (up to 25 windows = 75s)
    for i in range(10, 25):
        t = t0 + timedelta(seconds=3 * i)
        payload = RawTelemetryPayload(
            machine_id="physical_motor",
            device_id="esp32_serial",
            reading_id=f"win-phys-{i}",
            measured_at=t,
            operating_context=OperatingContext(source="physical"),
            readings=[
                SensorReading(sensor_id="temp_probe", parameter="temperature", value=48.0, unit="degC")
            ],
        )
        out = pipeline.process(payload)

    # Warm-up complete!
    assert out.detector_b_v2_result.status == DetectorBStatus.NORMAL
    assert out.detector_b_v2_result.model_type == ModelType.physical
    assert out.detector_b_v2_result.data_source == "physical"


def test_pipeline_simulator_telemetry_stream(dual_pipeline):
    pipeline = dual_pipeline
    t0 = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)

    # Ingest 25 windows of simulator telemetry
    for i in range(25):
        t = t0 + timedelta(seconds=3 * i)
        payload = RawTelemetryPayload(
            machine_id="sim_motor_01",
            device_id="simulator_inst",
            reading_id=f"win-sim-{i}",
            measured_at=t,
            operating_context=OperatingContext(source="simulator"),
            readings=[
                SensorReading(sensor_id="temp", parameter="motor_temperature", value=42.0, unit="degC"),
                SensorReading(sensor_id="vib", parameter="vibration_rms", value=1.2, unit="mm/s"),
                SensorReading(sensor_id="curr", parameter="mean_current", value=11.0, unit="A"),
            ],
        )
        out = pipeline.process(payload)

    assert out.detector_b_v2_result is not None
    assert out.detector_b_v2_result.status == DetectorBStatus.NORMAL
    assert out.detector_b_v2_result.model_type == ModelType.simulator
    assert out.detector_b_v2_result.data_source == "simulator"


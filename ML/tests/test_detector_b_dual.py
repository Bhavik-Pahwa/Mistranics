from datetime import datetime, timezone, timedelta
import numpy as np
import pytest
from ML.models.detector_b_schemas import DetectorBStatus, ModelType, DetectorBResult
from ML.detector_b.features_physical import PhysicalTelemetryPoint
from ML.detector_b.features_simulator import SimulatorTelemetryPoint
from ML.detector_b.data_physical import generate_physical_dataset, partition_dataset
from ML.detector_b.data_simulator import generate_simulator_dataset
from ML.detector_b.train_physical import PhysicalModelTrainer
from ML.detector_b.train_simulator import SimulatorModelTrainer
from ML.detector_b.dual_engine import DualIsolationForestEngine


@pytest.fixture(scope="module")
def trained_dual_engine():
    # 1. Train physical model
    phys_data = generate_physical_dataset(n_steps=120)
    phys_splits = partition_dataset(phys_data, train_ratio=0.55, val_ratio=0.25, gap_samples=10)
    phys_trainer = PhysicalModelTrainer(model_version="phys-v2.0")
    phys_pkg = phys_trainer.train(phys_splits["train_X"], phys_splits["val_X"], phys_splits["val_labels"])

    # 2. Train simulator model
    sim_data = generate_simulator_dataset(n_steps=150)
    sim_splits = partition_dataset(sim_data, train_ratio=0.55, val_ratio=0.25, gap_samples=10)
    sim_trainer = SimulatorModelTrainer(model_version="sim-v2.0")
    sim_pkg = sim_trainer.train(sim_splits["train_X"], sim_splits["val_X"], sim_splits["val_labels"])

    return DualIsolationForestEngine(physical_package=phys_pkg, simulator_package=sim_pkg)


def test_dual_engine_physical_dispatch_normal_and_anomaly(trained_dual_engine):
    engine = trained_dual_engine
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)

    # 1. 25 normal physical points (covers 60s warm-up)
    normal_history = [
        PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=3 * i), temperature=48.0)
        for i in range(25)
    ]
    t_eval = t0 + timedelta(seconds=72)
    res_normal = engine.evaluate_physical(normal_history, current_time=t_eval)

    assert res_normal.detector == "B"
    assert res_normal.model_type == ModelType.physical
    assert res_normal.data_source == "physical"
    assert res_normal.status == DetectorBStatus.NORMAL
    assert res_normal.anomaly_score is not None
    assert res_normal.decision_threshold is not None

    # 2. Sudden overheating anomaly (temperature jumps to 95°C)
    abnormal_history = list(normal_history)
    abnormal_history.append(
        PhysicalTelemetryPoint(timestamp=t_eval + timedelta(seconds=3), temperature=95.0)
    )
    res_abnormal = engine.evaluate_physical(abnormal_history, current_time=t_eval + timedelta(seconds=3))
    assert res_abnormal.status == DetectorBStatus.ANOMALY
    assert res_abnormal.anomaly_score <= res_abnormal.decision_threshold


def test_dual_engine_simulator_dispatch_normal_and_anomaly(trained_dual_engine):
    engine = trained_dual_engine
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)

    # 25 normal simulator points
    normal_history = [
        SimulatorTelemetryPoint(
            timestamp=t0 + timedelta(seconds=3 * i),
            temperature=42.0,
            vibration=1.3,
            current=11.5,
        )
        for i in range(25)
    ]
    t_eval = t0 + timedelta(seconds=72)
    res_normal = engine.evaluate_simulator(normal_history, current_time=t_eval)

    assert res_normal.detector == "B"
    assert res_normal.model_type == ModelType.simulator
    assert res_normal.data_source == "simulator"
    assert res_normal.status == DetectorBStatus.NORMAL

    # Imbalance & bearing anomaly (high vibration 6.5 mm/s, current 22.0A)
    abnormal_history = list(normal_history)
    abnormal_history.append(
        SimulatorTelemetryPoint(
            timestamp=t_eval + timedelta(seconds=3),
            temperature=55.0,
            vibration=6.5,
            current=22.0,
        )
    )
    res_abnormal = engine.evaluate_simulator(abnormal_history, current_time=t_eval + timedelta(seconds=3))
    assert res_abnormal.status == DetectorBStatus.ANOMALY


def test_dual_engine_source_routing(trained_dual_engine):
    engine = trained_dual_engine
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)

    phys_points = [
        PhysicalTelemetryPoint(timestamp=t0 + timedelta(seconds=3 * i), temperature=48.0)
        for i in range(25)
    ]
    # Route with source="physical"
    res1 = engine.evaluate(phys_points, source="physical", current_time=t0 + timedelta(seconds=72))
    assert res1.model_type == ModelType.physical

    sim_points = [
        SimulatorTelemetryPoint(
            timestamp=t0 + timedelta(seconds=3 * i),
            temperature=42.0,
            vibration=1.3,
            current=11.5,
        )
        for i in range(25)
    ]
    # Route with source="simulation"
    res2 = engine.evaluate(sim_points, source="simulation", current_time=t0 + timedelta(seconds=72))
    assert res2.model_type == ModelType.simulator


def test_dual_engine_missing_model_error():
    empty_engine = DualIsolationForestEngine(physical_package=None, simulator_package=None)
    t0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    points = [PhysicalTelemetryPoint(timestamp=t0, temperature=50.0)]
    res = empty_engine.evaluate(points, source="physical")
    assert res.status == DetectorBStatus.MODEL_ERROR

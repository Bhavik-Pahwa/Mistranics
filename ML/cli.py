import argparse
import json
import sys
import os
import numpy as np
from datetime import datetime, timezone, timedelta

from ML.models.telemetry import RawTelemetryPayload, SensorReading, OperatingContext
from ML.models.limits import ManufacturerLimitRecord, LimitVerificationStatus, LimitCategory, SourceReference
from ML.models.detector_b_schemas import ModelType, DetectorBStatus
from ML.detector_a.statistical_engine import StatisticalRuleConfig
from ML.detector_b.trainer import IsolationForestTrainer, load_model_package
from ML.detector_b.data_physical import generate_physical_dataset, partition_dataset
from ML.detector_b.data_simulator import generate_simulator_dataset
from ML.detector_b.train_physical import PhysicalModelTrainer
from ML.detector_b.train_simulator import SimulatorModelTrainer
from ML.detector_b.features_physical import PhysicalTelemetryPoint
from ML.detector_b.features_simulator import SimulatorTelemetryPoint
from ML.detector_b.dual_engine import DualIsolationForestEngine
from ML.pipeline import MachineHealthPipeline


def generate_synthetic_healthy_dataset(n_samples: int = 300) -> np.ndarray:
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(n_samples):
        row = [
            52.0 + rng.normal(0, 0.8),   # mean_temp
            51.5 + rng.normal(0, 0.8),   # min_temp
            52.5 + rng.normal(0, 0.8),   # max_temp
            11.5 + rng.normal(0, 0.3),   # mean_current
            1.6 + rng.normal(0, 0.08),   # vibration_rms
            2.2 + rng.normal(0, 0.1),    # peak_rms
            2.3 + rng.normal(0, 0.1),    # peak_vibration
            101.3 + rng.normal(0, 1.5),  # mean_pressure
            21.5 + rng.normal(0, 0.4),   # mean_output
            rng.normal(0, 0.1),          # temp_change_15s
            rng.normal(0, 0.2),          # temp_change_60s
            1.6 + rng.normal(0, 0.05),   # rolling_vib_15s
            1.6 + rng.normal(0, 0.05),   # rolling_vib_60s
            0.15 + rng.normal(0, 0.02),  # rolling_curr_std_15s
            0.15 + rng.normal(0, 0.02),  # rolling_curr_std_60s
            rng.normal(0, 0.05),         # pressure_roc
            1495.0 + rng.normal(0, 3.0), # rpm
            78.0 + rng.normal(0, 1.5),   # load
            1.0,                         # standard mode
            2.0,                         # running state
            1.0,                         # has_rpm
            1.0,                         # has_load
        ]
        rows.append(row)
    return np.array(rows)


def handle_train_physical(args):
    print(f"[*] Training Model 1: Physical Temperature Isolation Forest ({args.model_version})...")
    dataset = generate_physical_dataset(n_steps=args.steps)
    splits = partition_dataset(dataset, train_ratio=0.55, val_ratio=0.25, gap_samples=10)

    trainer = PhysicalModelTrainer(
        model_version=args.model_version,
        n_estimators=args.n_estimators,
    )
    pkg = trainer.train(splits["train_X"], splits["val_X"], splits["val_labels"])
    output_path = args.output
    pkg.save(output_path)
    print(f"[OK] Physical model saved successfully to: {output_path}")
    print(f"    - Metadata: {os.path.splitext(output_path)[0]}.json")
    print(f"    - Features: 12 (DS18B20 3s, 15s, 60s windows)")
    print(f"    - Decision threshold: {pkg.metadata.decision_threshold:.5f}")
    print(f"    - Training observations: {pkg.metadata.training_samples}")


def handle_train_simulator(args):
    print(f"[*] Training Model 2: Online Simulator Isolation Forest ({args.model_version})...")
    dataset = generate_simulator_dataset(n_steps=args.steps)
    splits = partition_dataset(dataset, train_ratio=0.55, val_ratio=0.25, gap_samples=10)

    trainer = SimulatorModelTrainer(
        model_version=args.model_version,
        n_estimators=args.n_estimators,
    )
    pkg = trainer.train(splits["train_X"], splits["val_X"], splits["val_labels"])
    output_path = args.output
    pkg.save(output_path)
    print(f"[OK] Simulator model saved successfully to: {output_path}")
    print(f"    - Metadata: {os.path.splitext(output_path)[0]}.json")
    print(f"    - Features: 36 (Temp, Vib, Curr across 3s, 15s, 60s)")
    print(f"    - Decision threshold: {pkg.metadata.decision_threshold:.5f}")
    print(f"    - Training observations: {pkg.metadata.training_samples}")


def handle_train(args):
    print(f"[*] Training Isolation Forest model: {args.model_version}...")
    X = generate_synthetic_healthy_dataset(n_samples=args.samples)
    trainer = IsolationForestTrainer(
        model_version=args.model_version,
        n_estimators=args.n_estimators,
        contamination=args.contamination,
    )
    pkg = trainer.train(X, val_ratio=0.2)
    output_path = args.output
    pkg.save(output_path)
    print(f"[OK] Model saved successfully to: {output_path}")
    print(f"    - Accompanying metadata: {os.path.splitext(output_path)[0]}.json")
    print(f"    - Decision threshold: {pkg.metadata.decision_threshold:.5f}")
    print(f"    - Training observations: {pkg.metadata.training_samples}")


def handle_simulate_dual(args):
    print(f"[*] Running Detector B v2.0 Dual Simulation ({args.steps} steps of 3s windows)...")
    
    # 1. Train or load both models
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

    dual_engine = DualIsolationForestEngine(physical_package=phys_pkg, simulator_package=sim_pkg)

    t0 = datetime.now(timezone.utc) - timedelta(seconds=args.steps * 3)

    phys_history = []
    sim_history = []

    for step in range(args.steps):
        t = t0 + timedelta(seconds=step * 3)
        is_anomaly = args.with_anomaly and step >= (args.steps - 3)

        # Physical reading (DS18B20)
        temp_phys = 92.0 if is_anomaly else 48.0
        phys_pt = PhysicalTelemetryPoint(timestamp=t, temperature=temp_phys, status="valid")
        phys_history.append(phys_pt)

        # Simulator reading (Temp, Vib, Curr)
        temp_sim = 82.0 if is_anomaly else 42.0
        vib_sim = 6.2 if is_anomaly else 1.3
        curr_sim = 24.0 if is_anomaly else 11.5
        sim_pt = SimulatorTelemetryPoint(
            timestamp=t, temperature=temp_sim, vibration=vib_sim, current=curr_sim, status="valid"
        )
        sim_history.append(sim_pt)

        # Evaluate both models independently
        res_phys = dual_engine.evaluate_physical(phys_history, current_time=t)
        res_sim = dual_engine.evaluate_simulator(sim_history, current_time=t)

        score_phys_str = f"{res_phys.anomaly_score:.4f}" if res_phys.anomaly_score is not None else "None"
        score_sim_str = f"{res_sim.anomaly_score:.4f}" if res_sim.anomaly_score is not None else "None"

        print(
            f"Step {step+1:02d} | Physical [12 feat]: status={res_phys.status.value:<17} "
            f"(Score={score_phys_str}) | "
            f"Simulator [36 feat]: status={res_sim.status.value:<17} "
            f"(Score={score_sim_str})"
        )


def handle_simulate(args):
    print(f"[*] Running Machine Health Engine simulation ({args.steps} steps of 3-second windows)...")
    
    trainer = IsolationForestTrainer(model_version="sim-iso-v1")
    X = generate_synthetic_healthy_dataset(n_samples=150)
    model_pkg = trainer.train(X, val_ratio=0.2)
    pipeline = MachineHealthPipeline(model_package=model_pkg)

    pipeline.detector_a.limits_engine.add_limit(
        ManufacturerLimitRecord(
            limit_id="lim-temp-max",
            machine_id="sim_machine_01",
            parameter="motor_temperature",
            upper_limit=75.0,
            unit="degC",
            category=LimitCategory.warning,
            status=LimitVerificationStatus.approved,
            source=SourceReference(document="OEM_Sim_Manual.pdf", page_or_section="p.12"),
        )
    )

    pipeline.detector_a.statistical_engine.add_rule(
        StatisticalRuleConfig(
            rule_id="stat-roc-high",
            parameter="motor_temperature",
            rate_of_change_threshold=5.0,
            persistence_count=2,
        )
    )

    t0 = datetime.now(timezone.utc) - timedelta(seconds=args.steps * 3)

    for step in range(args.steps):
        t = t0 + timedelta(seconds=step * 3)
        is_anomaly_step = args.with_anomaly and step >= (args.steps - 3)

        temp = 82.0 if is_anomaly_step else 52.0
        curr = 28.0 if is_anomaly_step else 11.5
        vib = 5.5 if is_anomaly_step else 1.6

        payload = RawTelemetryPayload(
            machine_id="sim_machine_01",
            device_id="esp32_sim",
            reading_id=f"win-{step:03d}",
            measured_at=t,
            operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
            readings=[
                SensorReading(sensor_id="s_temp", parameter="motor_temperature", value=temp, unit="degC"),
                SensorReading(sensor_id="s_curr", parameter="mean_current", value=curr, unit="A"),
                SensorReading(sensor_id="s_vib", parameter="vibration_rms", value=vib, unit="mm/s"),
                SensorReading(sensor_id="s_press", parameter="mean_pressure", value=100.0, unit="kPa"),
                SensorReading(sensor_id="s_out", parameter="mean_output", value=22.0, unit="kW"),
            ],
        )

        out = pipeline.process(payload)
        
        findings_count = sum(len(res.findings) for res in out.all_detector_results)
        score_val = out.isolation_forest_result.metrics.get('anomaly_score', 0.0) if out.isolation_forest_result else 0.0
        print(f"Step {step+1:02d} [{payload.reading_id}] -> Limits: {len(out.limits_result.findings)} findings | "
              f"Stats: {len(out.statistical_result.findings)} findings | "
              f"ML: {len(out.isolation_forest_result.findings)} findings "
              f"(Score: {score_val:.4f})")

        if findings_count > 0:
            for r in out.all_detector_results:
                for f in r.findings:
                    print(f"    >> [{r.detector.value}] Rule {f.rule_id}: {f.parameter}={f.observed_value} "
                          f"crossing threshold {f.threshold} ({f.direction})")


def main():
    parser = argparse.ArgumentParser(description="INDUX Machine Health Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Train command
    train_parser = subparsers.add_parser("train", help="Train default Isolation Forest model")
    train_parser.add_argument("--output", type=str, default="ML/models/model_artifacts/isolation_forest.joblib")
    train_parser.add_argument("--model-version", type=str, default="iso-v1.0")
    train_parser.add_argument("--samples", type=int, default=300)
    train_parser.add_argument("--n-estimators", type=int, default=100)
    train_parser.add_argument("--contamination", type=str, default="auto")

    # Train physical command (Model 1)
    train_phys = subparsers.add_parser("train-physical", help="Train Model 1: Physical DS18B20 Isolation Forest (12 features)")
    train_phys.add_argument("--output", type=str, default="ML/models/model_artifacts/physical_isolation_forest.joblib")
    train_phys.add_argument("--model-version", type=str, default="physical-iso-v2.0")
    train_phys.add_argument("--steps", type=int, default=200)
    train_phys.add_argument("--n-estimators", type=int, default=200)

    # Train simulator command (Model 2)
    train_sim = subparsers.add_parser("train-simulator", help="Train Model 2: Online Simulator Isolation Forest (36 features)")
    train_sim.add_argument("--output", type=str, default="ML/models/model_artifacts/simulator_isolation_forest.joblib")
    train_sim.add_argument("--model-version", type=str, default="simulator-iso-v2.0")
    train_sim.add_argument("--steps", type=int, default=250)
    train_sim.add_argument("--n-estimators", type=int, default=200)

    # Simulate command
    sim_parser = subparsers.add_parser("simulate", help="Simulate telemetry stream through pipeline")
    sim_parser.add_argument("--steps", type=int, default=10)
    sim_parser.add_argument("--with-anomaly", action="store_true", help="Inject anomaly in the final steps")

    # Simulate dual command (PRD v2.0)
    sim_dual = subparsers.add_parser("simulate-dual", help="Simulate both Physical and Simulator models through Detector B v2.0")
    sim_dual.add_argument("--steps", type=int, default=25, help="Number of steps (>= 22 to cover 60s warm-up)")
    sim_dual.add_argument("--with-anomaly", action="store_true", help="Inject anomaly in the final steps")

    args = parser.parse_args()
    if args.command == "train":
        handle_train(args)
    elif args.command == "train-physical":
        handle_train_physical(args)
    elif args.command == "train-simulator":
        handle_train_simulator(args)
    elif args.command == "simulate":
        handle_simulate(args)
    elif args.command == "simulate-dual":
        handle_simulate_dual(args)


if __name__ == "__main__":
    main()

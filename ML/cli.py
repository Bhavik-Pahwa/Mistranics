import argparse
import json
import sys
import os
import numpy as np
from datetime import datetime, timezone, timedelta

from ML.models.telemetry import RawTelemetryPayload, SensorReading, OperatingContext
from ML.models.limits import ManufacturerLimitRecord, LimitVerificationStatus, LimitCategory, SourceReference
from ML.detector_a.statistical_engine import StatisticalRuleConfig
from ML.detector_b.trainer import IsolationForestTrainer, load_model_package
from ML.pipeline import MachineHealthPipeline
from ML.simulation import motor_temperature


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


def handle_simulate(args):
    print(f"[*] Running Machine Health Engine simulation ({args.steps} steps of 3-second windows)...")
    
    # Train or load model
    trainer = IsolationForestTrainer(model_version="sim-iso-v1")
    X = generate_synthetic_healthy_dataset(n_samples=150)
    model_pkg = trainer.train(X, val_ratio=0.2)
    pipeline = MachineHealthPipeline(model_package=model_pkg)

    # Configure sample approved limit
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

    # Configure sample statistical rule
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

        temp = motor_temperature(step, args.steps, args.with_anomaly)
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
        print(f"Step {step+1:02d} [{payload.reading_id}] -> Limits: {len(out.limits_result.findings)} findings | "
              f"Stats: {len(out.statistical_result.findings)} findings | "
              f"ML: {len(out.isolation_forest_result.findings)} findings "
              f"(Score: {out.isolation_forest_result.metrics.get('anomaly_score', 0.0):.4f})")

        if findings_count > 0:
            for r in out.all_detector_results:
                for f in r.findings:
                    print(f"    >> [{r.detector.value}] Rule {f.rule_id}: {f.parameter}={f.observed_value} "
                          f"crossing threshold {f.threshold} ({f.direction})")


def main():
    parser = argparse.ArgumentParser(description="INDUX Machine Health Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Train command
    train_parser = subparsers.add_parser("train", help="Train Isolation Forest model")
    train_parser.add_argument("--output", type=str, default="ML/models/model_artifacts/isolation_forest.joblib")
    train_parser.add_argument("--model-version", type=str, default="iso-v1.0")
    train_parser.add_argument("--samples", type=int, default=300)
    train_parser.add_argument("--n-estimators", type=int, default=100)
    train_parser.add_argument("--contamination", type=str, default="auto")

    # Simulate command
    sim_parser = subparsers.add_parser("simulate", help="Simulate telemetry stream through pipeline")
    sim_parser.add_argument("--steps", type=int, default=10)
    sim_parser.add_argument("--with-anomaly", action="store_true", help="Inject anomaly in the final steps")

    args = parser.parse_args()
    if args.command == "train":
        handle_train(args)
    elif args.command == "simulate":
        handle_simulate(args)


if __name__ == "__main__":
    main()

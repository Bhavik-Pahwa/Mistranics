from datetime import datetime, timezone, timedelta
import numpy as np
import pytest
from ML.models.telemetry import RawTelemetryPayload, SensorReading, OperatingContext
from ML.models.limits import ManufacturerLimitRecord, LimitVerificationStatus, LimitCategory, SourceReference
from ML.models.results import DetectorType, EvaluationStatus
from ML.detector_a.statistical_engine import StatisticalRuleConfig
from ML.detector_b.trainer import IsolationForestTrainer
from ML.pipeline import MachineHealthPipeline


@pytest.fixture
def trained_pipeline():
    # 1. Train an Isolation Forest model on 100 healthy synthetic records
    rng = np.random.default_rng(42)
    X_healthy = []
    for _ in range(100):
        # Normal machine behavior
        row = [
            50.0 + rng.normal(0, 0.5),   # mean_temp
            49.5 + rng.normal(0, 0.5),   # min_temp
            50.5 + rng.normal(0, 0.5),   # max_temp
            10.0 + rng.normal(0, 0.2),   # mean_current
            1.5 + rng.normal(0, 0.05),   # vibration_rms
            2.1 + rng.normal(0, 0.1),    # peak_rms
            2.1 + rng.normal(0, 0.1),    # peak_vibration
            100.0 + rng.normal(0, 1.0),  # mean_pressure
            20.0 + rng.normal(0, 0.5),   # mean_output
            rng.normal(0, 0.1),          # temp_change_15s
            rng.normal(0, 0.2),          # temp_change_60s
            1.5 + rng.normal(0, 0.05),   # rolling_vib_15s
            1.5 + rng.normal(0, 0.05),   # rolling_vib_60s
            0.1 + rng.normal(0, 0.02),   # rolling_curr_std_15s
            0.1 + rng.normal(0, 0.02),   # rolling_curr_std_60s
            rng.normal(0, 0.1),          # pressure_roc
            1500.0 + rng.normal(0, 2.0), # rpm
            80.0 + rng.normal(0, 1.0),   # load
            1.0,                         # standard mode
            2.0,                         # running state
            1.0,                         # has_rpm
            1.0,                         # has_load
        ]
        X_healthy.append(row)

    trainer = IsolationForestTrainer(model_version="pipe-iso-v1.0")
    model_pkg = trainer.train(np.array(X_healthy), val_ratio=0.2)

    # 2. Setup pipeline
    pipeline = MachineHealthPipeline(model_package=model_pkg)

    # 3. Add approved manufacturer limit: max temp 75.0 degC
    source = SourceReference(document="OEM_Spec.pdf", page_or_section="p.10")
    pipeline.detector_a.limits_engine.add_limit(
        ManufacturerLimitRecord(
            limit_id="lim-max-temp",
            machine_id="machine_alpha",
            parameter="motor_temperature",
            upper_limit=75.0,
            unit="degC",
            category=LimitCategory.warning,
            status=LimitVerificationStatus.approved,
            source=source,
        )
    )

    # 4. Add statistical rule: rate of change > 4.0 °C/min
    pipeline.detector_a.statistical_engine.add_rule(
        StatisticalRuleConfig(
            rule_id="stat-temp-roc",
            parameter="motor_temperature",
            rate_of_change_threshold=4.0,
            persistence_count=2,
        )
    )

    return pipeline


def test_end_to_end_stream_processing(trained_pipeline):
    pipeline = trained_pipeline
    t0 = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)

    # Feed 5 normal windows (first 15 seconds)
    for i in range(5):
        t = t0 + timedelta(seconds=3 * i)
        payload = RawTelemetryPayload(
            machine_id="machine_alpha",
            device_id="iot_gw_1",
            reading_id=f"win-norm-{i}",
            measured_at=t,
            operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
            readings=[
                SensorReading(sensor_id="temp", parameter="motor_temperature", value=50.0, unit="degC"),
                SensorReading(sensor_id="curr", parameter="mean_current", value=10.0, unit="A"),
                SensorReading(sensor_id="vib", parameter="vibration_rms", value=1.5, unit="mm/s"),
                SensorReading(sensor_id="press", parameter="mean_pressure", value=100.0, unit="kPa"),
                SensorReading(sensor_id="out", parameter="mean_output", value=20.0, unit="kW"),
            ]
        )
        out = pipeline.process(payload)
        assert out.validation_status.is_valid is True
        assert out.limits_result.status == EvaluationStatus.completed
        assert len(out.limits_result.findings) == 0

    # Window 6: Temperature jumps to 80.0 °C (exceeds 75.0 limit, roc > 4.0, and unusual combination for ML)
    t_anomaly = t0 + timedelta(seconds=15)
    anomaly_payload = RawTelemetryPayload(
        machine_id="machine_alpha",
        device_id="iot_gw_1",
        reading_id="win-anomaly-1",
        measured_at=t_anomaly,
        operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
        readings=[
            SensorReading(sensor_id="temp", parameter="motor_temperature", value=80.0, unit="degC"),
            SensorReading(sensor_id="curr", parameter="mean_current", value=25.0, unit="A"),
            SensorReading(sensor_id="vib", parameter="vibration_rms", value=6.0, unit="mm/s"),
            SensorReading(sensor_id="press", parameter="mean_pressure", value=150.0, unit="kPa"),
            SensorReading(sensor_id="out", parameter="mean_output", value=40.0, unit="kW"),
        ]
    )
    anomaly_out = pipeline.process(anomaly_payload)

    # 1. Detector A - Limits: should detect max temp exceeded
    assert len(anomaly_out.limits_result.findings) == 1
    assert anomaly_out.limits_result.findings[0].rule_id == "lim-max-temp"
    assert anomaly_out.limits_result.findings[0].observed_value == 80.0

    # 2. Detector A - Statistical: persistence count is 2, this is the 1st violation
    assert len(anomaly_out.statistical_result.findings) == 0

    # Missing real extrema/peaks and incomplete 60s history must not be invented.
    assert anomaly_out.isolation_forest_result.status == EvaluationStatus.insufficient_data
    assert anomaly_out.isolation_forest_result.findings == []

    # Window 7: 2nd consecutive violation window satisfies statistical persistence!
    t_anomaly_2 = t0 + timedelta(seconds=18)
    anomaly_payload_2 = RawTelemetryPayload(
        machine_id="machine_alpha",
        device_id="iot_gw_1",
        reading_id="win-anomaly-2",
        measured_at=t_anomaly_2,
        operating_context=OperatingContext(operating_state="running", operating_mode="standard", rpm=1500.0, load_percentage=80.0),
        readings=[
            SensorReading(sensor_id="temp", parameter="motor_temperature", value=82.0, unit="degC"),
            SensorReading(sensor_id="curr", parameter="mean_current", value=25.0, unit="A"),
            SensorReading(sensor_id="vib", parameter="vibration_rms", value=6.0, unit="mm/s"),
            SensorReading(sensor_id="press", parameter="mean_pressure", value=150.0, unit="kPa"),
            SensorReading(sensor_id="out", parameter="mean_output", value=40.0, unit="kW"),
        ]
    )
    out_2 = pipeline.process(anomaly_payload_2)
    assert len(out_2.statistical_result.findings) >= 1
    assert out_2.statistical_result.findings[0].rule_id == "stat-temp-roc"


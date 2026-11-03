from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from ML.models.detector_b_schemas import (
    DetectorBStatus,
    ModelType,
    DetectorBResult,
    PHYSICAL_FEATURE_COLUMNS,
    SIMULATOR_FEATURE_COLUMNS,
)


def test_feature_column_definitions():
    assert len(PHYSICAL_FEATURE_COLUMNS) == 12
    assert len(SIMULATOR_FEATURE_COLUMNS) == 36

    # Verify physical columns
    assert PHYSICAL_FEATURE_COLUMNS[0] == "temp_mean_3s"
    assert PHYSICAL_FEATURE_COLUMNS[3] == "temp_std_3s"
    assert PHYSICAL_FEATURE_COLUMNS[4] == "temp_mean_15s"
    assert PHYSICAL_FEATURE_COLUMNS[8] == "temp_mean_60s"

    # Verify simulator columns (temp, vib, curr for 3s, 15s, 60s)
    assert SIMULATOR_FEATURE_COLUMNS[0] == "temp_mean_3s"
    assert SIMULATOR_FEATURE_COLUMNS[4] == "vib_mean_3s"
    assert SIMULATOR_FEATURE_COLUMNS[8] == "curr_mean_3s"
    assert SIMULATOR_FEATURE_COLUMNS[12] == "temp_mean_15s"
    assert SIMULATOR_FEATURE_COLUMNS[24] == "temp_mean_60s"


def test_detector_b_result_schema_valid():
    now = datetime(2026, 11, 3, 10, 30, 0, tzinfo=timezone.utc)
    res = DetectorBResult(
        detector="B",
        model_type=ModelType.physical,
        model_version="1.0",
        timestamp=now,
        anomaly_score=-0.15,
        decision_threshold=-0.10,
        status=DetectorBStatus.ANOMALY,
        data_source="physical",
    )
    assert res.detector == "B"
    assert res.model_type == ModelType.physical
    assert res.status == DetectorBStatus.ANOMALY
    assert res.anomaly_score == -0.15
    assert res.decision_threshold == -0.10

    # Test serialization conforms to PRD section 9.3
    d = res.model_dump(mode="json")
    assert d["detector"] == "B"
    assert d["model_type"] == "physical"
    assert d["model_version"] == "1.0"
    assert d["status"] == "ANOMALY"
    assert d["data_source"] == "physical"


def test_detector_b_result_insufficient_data():
    now = datetime.now(timezone.utc)
    res = DetectorBResult(
        detector="B",
        model_type=ModelType.simulator,
        model_version="1.0",
        timestamp=now,
        anomaly_score=None,
        decision_threshold=-0.08,
        status=DetectorBStatus.INSUFFICIENT_DATA,
        data_source="simulator",
    )
    assert res.status == DetectorBStatus.INSUFFICIENT_DATA
    assert res.anomaly_score is None


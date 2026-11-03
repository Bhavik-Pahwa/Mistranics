import os
import pytest
from sqlalchemy import event, MetaData
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.services import load_registry, seed
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        database_url=os.getenv(
            "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db")
        ),
        registry_file="examples/registry.json",
        policy_file="examples/demo-policy.json",
        api_token="read",
        internal_token="internal",
        operator_token="operator",
        mqtt_enabled=False,
        retry_seconds=1,
        iot_enabled=False,
    )
    app = create_app(settings)
    engine = app.state.engine
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    reflected = MetaData()
    reflected.reflect(bind=engine)
    reflected.drop_all(engine)
    Base.metadata.create_all(engine)
    with app.state.factory.begin() as session:
        seed(session, load_registry(settings.registry_file))
    yield app
    reflected = MetaData()
    reflected.reflect(bind=engine)
    reflected.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer read"
        yield client


@pytest.fixture
def telemetry():
    return {
        "schema_version": "1.0",
        "machine_id": "motor_001",
        "device_id": "esp32_001",
        "reading_id": "window-1",
        "measured_at": "2026-11-02T09:10:03Z",
        "readings": [
            {
                "sensor_id": "temp_01",
                "parameter": "motor_temperature",
                "value": 56.4,
                "unit": "degC",
            }
        ],
    }


def detector(kind="manufacturer_limits", **overrides):
    result = {
        "schema_version": "1.0",
        "machine_id": "motor_001",
        "window_id": "window-1",
        "run_id": "run-1",
        "detector": kind,
        "evaluated_at": "2026-11-02T09:10:04Z",
        "status": "completed",
        "findings": [],
        "data_quality": {"status": "valid", "warnings": []},
        "model_or_config_version": "v1",
    }
    if kind == "isolation_forest":
        result.update(model_version="model-1", feature_schema_version="features-1")
    else:
        result["config_version"] = "config-1"
    return result | overrides

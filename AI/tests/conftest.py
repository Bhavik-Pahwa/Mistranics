import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.db import Base
from backend.app.main import create_app
from backend.app.services import seed, load_registry
from AI.provider import ProviderError

ROOT = Path(__file__).resolve().parents[2]


class FakeProvider:
    """Test-only deterministic provider; application code always calls real Ollama."""

    def __init__(self):
        self.mode = "valid"
        self.calls = []

    def embed(self, texts):
        return [
            [
                1.0,
                float("pressure" in text.lower()),
                float("temperature" in text.lower()),
            ]
            for text in texts
        ]

    def chat(self, messages, schema):
        self.calls.append(messages)
        if self.mode == "timeout":
            raise ProviderError(
                "AI provider unavailable or timed out; retry is available"
            )
        if self.mode == "invalid":
            return "not json"
        data = json.loads(messages[1]["content"])
        passages = data["manufacturer_passages"]
        sources, instructions = [], []
        if passages:
            passage = passages[0]
            source = {
                k: passage[k] for k in ["chunk_id", "document_id", "version", "page"]
            }
            sources = [source]
            instructions = [
                {
                    "title": "Review manufacturer procedure",
                    "description": passage["text"],
                    "source_quote": passage["text"],
                    "source": source,
                    "requires_technician": True,
                }
            ]
        return json.dumps(
            {
                "response_type": "TROUBLESHOOTING",
                "condition_summary": "Further investigation is needed; a mechanical failure is not confirmed.",
                "possible_causes": [],
                "instructions": instructions,
                "missing_information": [],
                "safety_warnings": [],
                "sources": sources,
            }
        )


@pytest.fixture
def system(tmp_path):
    settings = Settings(
        database_url=os.getenv(
            "TEST_AI_DATABASE_URL", "sqlite:///" + str(tmp_path / "ai.db")
        ),
        registry_file=str(ROOT / "backend/examples/registry.json"),
        internal_token="internal",
        operator_token="operator",
        api_token="read",
        ml_enabled=True,
        ai_enabled=True,
        mqtt_enabled=False,
        ai_llm_model="test-only",
        ai_embedding_model="test-embedding",
        retry_seconds=1,
    )
    app = create_app(settings)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with app.state.factory.begin() as db:
        seed(db, load_registry(settings.registry_file))
    fake = FakeProvider()
    app.state.troubleshooting.provider = fake
    # Service processing is explicitly advanced by tests. Live lifespan is covered separately.
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer operator"
    yield app, client, fake, settings
    client.close()
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


@pytest.fixture
def pdf():
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (40, 50),
        "PRESSURE REGULATOR\nValve-X19: Use an authorized technician to review the pressure regulator.\nReference pressure table: nominal 10 bar; documentation only.",
    )
    content = document.tobytes()
    document.close()
    return content


def telemetry(window="w1", temperature=80.0, vibration=2.0, at=None):
    from backend.app.db import now

    return {
        "schema_version": "1.0",
        "machine_id": "motor_001",
        "device_id": "esp32_001",
        "reading_id": window,
        "measured_at": (at or now()).isoformat(),
        "readings": [
            {
                "sensor_id": "temp_01",
                "parameter": "motor_temperature",
                "value": temperature,
                "unit": "degC",
            },
            {
                "sensor_id": "vib_01",
                "parameter": "vibration_velocity_rms",
                "value": vibration,
                "unit": "mm/s",
            },
        ],
    }


def approve_limit(app, parameter="motor_temperature", unit="degC", upper=75.0):
    from ML.models.limits import ManufacturerLimitRecord

    app.state.classical.pipeline.detector_a.limits_engine.add_limit(
        ManufacturerLimitRecord(
            limit_id="test-" + parameter,
            machine_id="motor_001",
            parameter=parameter,
            upper_limit=upper,
            unit=unit,
            status="approved",
            reviewer="TEST ONLY",
            source={"document": "synthetic test manual"},
            config_version="test-v1",
        )
    )

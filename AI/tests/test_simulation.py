import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from AI.provider import generation_schema
from AI.schemas import Answer
from AI.rag import extract_pdf
from backend.app.config import Settings
from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_generation_schema_keeps_validation_schema_intact():
    original = Answer.model_json_schema()
    converted = generation_schema(original)
    assert "maxLength" not in json.dumps(converted)
    assert original["$defs"]["Instruction"]["properties"]["description"]["maxLength"] == 3000
    assert converted["$defs"]["Instruction"]["properties"]["source"]["$ref"] == original["$defs"]["Instruction"]["properties"]["source"]["$ref"]
    assert converted["additionalProperties"] is False


def test_fictional_manuals_cover_every_simulator_mode_and_edge_case():
    manifest = json.loads((ROOT / "output/pdf/simulation-manuals.json").read_text())
    assert len(manifest) == 3
    handbook = next(d for d in manifest if d["document_id"] == "SIM-MTR-FAULTS")
    assert set(handbook["modes"]) == {"normal", "imb", "mis", "brg", "loose", "heat", "over", "short", "stall"}
    settings = Settings(_env_file=None)
    for manual in manifest:
        assert manual["fictional"] is True
        assert manual["asset_id"] == "simulation-01"
        chunks = extract_pdf((ROOT / "output/pdf" / manual["filename"]).read_bytes(), settings)
        text = "\n".join(c["text"] for c in chunks).casefold()
        assert "fictional training manual" in text
        assert "not approved" in text
        assert "sensor error" in text and "stale" in text and "baseline" in text
    chunks = extract_pdf((ROOT / "output/pdf" / handbook["filename"]).read_bytes(), settings)
    assert {c["page"] for c in chunks} == set(range(1, 12))


def test_unconfigured_knowledge_is_explicit_and_physical_machine_is_rejected(tmp_path):
    app = create_app(Settings(_env_file=None, iot_enabled=True, mqtt_enabled=False,
                              ai_enabled=True, ai_llm_model="", ai_embedding_model="",
                              simulator_publish_enabled=False,
                              simulation_knowledge_database=str(tmp_path / "knowledge.db")))
    with TestClient(app) as client:
        app.state.simulation_knowledge.thread.join(timeout=2)
        state = client.get("/api/industrial/knowledge").json()
        assert state["status"] == "error" and "Configure" in state["error"]
        assert client.post("/api/industrial/chat", json={"text": "inspect bearing"}).status_code == 503
        assert client.post("/api/industrial/chat", json={"machine_id": "device-01", "text": "inspect bearing"}).status_code == 422
        assert client.get("/api/industrial/manuals/unknown/pdf").status_code == 404


@pytest.mark.parametrize("text", ["", "x" * 4001])
def test_simulation_questions_are_bounded(text):
    from pydantic import ValidationError
    from AI.simulation import Question
    with pytest.raises(ValidationError):
        Question(text=text)

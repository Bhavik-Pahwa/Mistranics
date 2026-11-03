"""Industrial prototype adapter for the existing real RAG and Ollama pipeline.

Uses AI.rag ingestion/retrieval and AI.reasoning validation unchanged. This local
corpus is explicitly fictional and is never promoted to approved machine limits.
"""
import json
import logging
import threading
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func

from backend.app.db import Base, Asset, connect
from backend.app.services import DomainError
from .models import Manual, Chunk
from .provider import OllamaProvider, ProviderError
from .rag import ingest_manual, retrieve
from .reasoning import reason, InvalidAnswer

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str = "simulation-01"
    text: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=10)


class SimulationKnowledge:
    def __init__(self, settings, telemetry):
        self.settings, self.telemetry = settings, telemetry
        self.provider = OllamaProvider(settings)
        self.lock, self.inference = threading.RLock(), threading.Lock()
        self.status, self.error = "starting", None
        self.documents, self.thread = [], None
        directory = Path(settings.simulation_manual_dir)
        self.directory = directory if directory.is_absolute() else ROOT / directory
        database = Path(settings.simulation_knowledge_database)
        self.database = database if database.is_absolute() else ROOT / database
        self.engine = self.factory = None

    def start(self):
        self.thread = threading.Thread(target=self.initialize, name="simulation-knowledge", daemon=True)
        self.thread.start()

    def initialize(self):
        try:
            if not self.settings.ai_llm_model or not self.settings.ai_embedding_model:
                raise ProviderError("Configure AI_LLM_MODEL and AI_EMBEDDING_MODEL")
            manifest = json.loads((self.directory / "simulation-manuals.json").read_text(encoding="utf-8"))
            self.database.parent.mkdir(parents=True, exist_ok=True)
            self.engine, self.factory = connect("sqlite:///" + self.database.as_posix())
            Base.metadata.create_all(self.engine)
            with self.factory.begin() as db:
                if not db.get(Asset, "simulation-01"):
                    db.add(Asset(asset_id="simulation-01", name="Prototype motor", metadata_json={
                        "manufacturer": "Mistranics fictional training",
                        "machine_model": "Simulator.html",
                        "documentation_scope": "simulation_training",
                    }))
            with self.lock:
                self.status = "indexing"
            for document in manifest:
                with self.factory.begin() as db:
                    manual, _ = ingest_manual(db, self.provider, self.settings,
                        (self.directory / document["filename"]).read_bytes(),
                        document["document_id"], document["version"], "simulation-01",
                        "Mistranics fictional training", "Simulator.html")
                    count = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.manual_id == manual.id))
                with self.lock:
                    self.documents.append(document | {"chunks": count, "url": "/api/industrial/manuals/" + document["document_id"] + "/pdf"})
            with self.lock:
                self.status = "ready"
            log.info("Simulation manuals indexed documents=%s chunks=%s", len(self.documents), sum(d["chunks"] for d in self.documents))
        except Exception as exc:
            log.exception("Simulation knowledge initialization failed")
            with self.lock:
                self.status, self.error = "error", str(exc)

    def snapshot(self):
        with self.lock:
            return dict(status=self.status, error=self.error, fictional=True,
                        llm_model=self.settings.ai_llm_model, embedding_model=self.settings.ai_embedding_model,
                        document_count=len(self.documents), chunk_count=sum(d["chunks"] for d in self.documents),
                        documents=list(self.documents))

    def context(self):
        state = self.telemetry.snapshot()
        latest = state["latest"]
        references = []
        observations = []
        if latest:
            references.append("reading:" + str(latest["sequence"]))
            observations = [{"sensor": key, "value": r["mean"], "unit": r["unit"],
                             "status": r["status"], "detection": r["anomaly"]["status"]}
                            for key, r in latest["readings"].items()]
        return dict(machine={"asset_id": "simulation-01", "name": "Prototype motor"},
                    documentation_scope="simulation_training", fictional_manuals=True,
                    selected_context=["manual", "readings"], references=references,
                    limitations=[] if state["stream_status"] == "LIVE" else ["No fresh simulator telemetry is available; interpret this as a documentation question"],
                    telemetry_stale=state["stream_status"] != "LIVE", mqtt_connected=state["mqtt_connected"],
                    timestamp=latest["timestamp"] if latest else None, observations=observations,
                    approved_limits=[])

    def passages(self, question):
        if self.snapshot()["status"] != "ready":
            raise ProviderError(self.error or "Simulation manuals are still indexing")
        session = SimpleNamespace(asset_id="simulation-01", document_id="SIM-MTR-FAULTS", document_version="simulation-v1")
        with self.factory.begin() as db:
            passages, limitation = retrieve(db, self.provider, self.settings, session, question, limit=6)
            if not passages:
                return passages, limitation
            # Expand the top retrieved fault page to its procedure section. A
            # symptom paragraph alone often outranks the adjacent actual checks.
            first = passages[0]
            manual = db.scalar(select(Manual).where(Manual.document_id == first["document_id"], Manual.version == first["version"], Manual.asset_id == session.asset_id))
            checks = db.scalar(select(Chunk).where(Chunk.manual_id == manual.id, Chunk.page == first["page"], Chunk.section.like("%VIRTUAL TROUBLESHOOTING CHECKS%")))
            if checks:
                procedure = first | {"chunk_id": checks.id, "page": checks.page, "section": checks.section, "text": checks.text}
                # Bounded parent-page context keeps the small local model focused.
                additional = next((p for p in passages if p["page"] == first["page"] and p["chunk_id"] != checks.id), None)
                return [procedure] + ([additional] if additional else []), limitation
            return passages[:2], limitation

    def ask(self, payload):
        if payload.machine_id != "simulation-01":
            raise DomainError("These fictional manuals apply only to the Prototype motor", 422)
        if not self.inference.acquire(blocking=False):
            raise DomainError("A local model request is already running; try again shortly", 409)
        try:
            passages, limitation = self.passages(payload.text)
            context = self.context()
            if limitation:
                context["limitations"].append(limitation)
            # Conversation text is data, never additional system instructions.
            history = [{"role": m["role"], "content": m.get("text", m.get("content", ""))[:4000]}
                       for m in payload.history if m.get("role") in ("user", "assistant")]
            answer = reason(self.provider, payload.text, history, context, passages)
            if passages and not answer.sources:
                raise InvalidAnswer("The model did not cite retrieved evidence; no grounded answer was accepted")
            result = answer.model_dump(mode="json")
            result.update(model=self.settings.ai_llm_model, embedding_model=self.settings.ai_embedding_model,
                          fictional=True, machine_context=context, evidence=passages,
                          pipeline="AI.rag.retrieve -> AI.reasoning.reason -> OllamaProvider.chat")
            return result
        finally:
            self.inference.release()

    def stop(self):
        if self.thread:
            self.thread.join(timeout=2)
        if self.engine and not (self.thread and self.thread.is_alive()):
            self.engine.dispose()


def install_simulation_knowledge(app, settings, telemetry):
    knowledge = SimulationKnowledge(settings, telemetry)
    app.state.simulation_knowledge = knowledge

    @app.get("/api/industrial/knowledge")
    def status():
        return knowledge.snapshot()

    @app.get("/api/industrial/manuals")
    def manuals():
        return knowledge.snapshot()

    @app.get("/api/industrial/manuals/{document_id}/pdf")
    def pdf(document_id: str):
        document = next((d for d in knowledge.snapshot()["documents"] if d["document_id"] == document_id), None)
        if not document:
            raise HTTPException(404, "Simulation manual not found")
        return FileResponse(knowledge.directory / document["filename"], media_type="application/pdf", filename=document["filename"], content_disposition_type="inline")

    @app.post("/api/industrial/chat")
    def chat(payload: Question):
        try:
            return knowledge.ask(payload)
        except DomainError as exc:
            raise HTTPException(exc.status, exc.detail) from exc
        except (ProviderError, InvalidAnswer) as exc:
            raise HTTPException(503, str(exc)) from exc
    return knowledge

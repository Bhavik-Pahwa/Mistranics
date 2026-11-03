"""Opt-in real Ollama/RAG acceptance run; no generated embeddings or fake provider.

Run from the repository root. Uses current simulator telemetry from the running
backend and writes a reviewable report. Does not change simulator controls.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from AI.simulation import SimulationKnowledge, Question
from backend.app.config import Settings

QUESTIONS = {
    "normal": ("normal operation and baseline drift", "What virtual checks explain a temperature deviation during normal operation and baseline warm-up?"),
    "imb": ("rotor imbalance", "What virtual troubleshooting checks distinguish rotor imbalance with radial once-per-revolution acceleration?"),
    "mis": ("shaft and coupling misalignment", "What virtual troubleshooting checks distinguish shaft and coupling misalignment with axial twice-per-revolution motion?"),
    "brg": ("bearing fault and friction impulses", "What virtual checks distinguish bearing fault periodic impulses, decaying oscillations and friction heating?"),
    "loose": ("loose mounting and irregular knocks", "What virtual checks distinguish loose mounting with irregular knocks and a half-frequency rattle?"),
    "heat": ("overheating and reduced cooling", "What virtual troubleshooting checks distinguish overheating and reduced cooling with a sustained thermal rise?"),
    "over": ("overload and excess shaft torque", "What virtual troubleshooting checks distinguish overload and excess shaft torque with high mean current?"),
    "short": ("winding short and electrical ripple", "What virtual checks distinguish winding short and electrical ripple with a fixed-frequency hum?"),
    "stall": ("stall and near-locked rotor", "What virtual checks distinguish stall and near-locked rotor with high current and low vibration?"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None)
    parser.add_argument("--modes", default=",".join(QUESTIONS))
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Retain already validated real answers and retry remaining cases")
    args = parser.parse_args()
    class CurrentSimulator:
        def snapshot(self):
            with urllib.request.urlopen(args.backend + "/api/status?source=simulation", timeout=5) as response:
                return json.load(response)
    settings = Settings(ai_llm_model=args.model or Settings().ai_llm_model or "llama3.2:1b", ai_embedding_model="nomic-embed-text", ai_provider_timeout=180,
                        simulation_knowledge_database=".iot-test/simulation-rag-acceptance.sqlite3")
    knowledge = SimulationKnowledge(settings, CurrentSimulator())
    knowledge.initialize()
    status = knowledge.snapshot()
    print(json.dumps({"index": {k: v for k, v in status.items() if k != "documents"}}), flush=True)
    if status["status"] != "ready":
        raise RuntimeError(status["error"])
    report_path = ROOT / ".iot-test" / "simulation-rag-acceptance.json"
    results = []
    if args.resume and report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        results = [r for r in previous["results"] if r.get("retrieval_passed") and r.get("answer_passed")]
    for mode in args.modes.split(","):
        if any(r["mode"] == mode for r in results):
            print(json.dumps({"mode": mode, "retained_validated_real_answer": True}), flush=True)
            continue
        expected, question = QUESTIONS[mode]
        started = time.monotonic()
        result = dict(mode=mode, question=question)
        try:
            passages, limitation = knowledge.passages(question)
            expected_page = list(QUESTIONS).index(mode) + 2
            relevant = any(p["page"] == expected_page for p in passages)
            result.update(retrieval_passed=relevant, retrieved_pages=[p["page"] for p in passages], limitation=limitation)
            if not relevant:
                raise AssertionError("Relevant fault section was not retrieved")
            if not args.retrieval_only:
                answer = knowledge.ask(Question(text=question))
                assert answer["sources"], "No validated citations"
                assert answer["instructions"], "No source-backed troubleshooting checks"
                assert any(s["page"] == expected_page for s in answer["sources"]), "Answer did not cite the relevant fault page"
                result.update(answer_passed=True, answer=answer)
        except Exception as exc:
            result.update(error=str(exc), answer_passed=False)
        result["duration_seconds"] = round(time.monotonic() - started, 2)
        results.append(result)
        report = dict(provider="real local Ollama", index=status, results=results)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "answer"}), flush=True)
    knowledge.stop()
    return 0 if all(r.get("retrieval_passed") and (args.retrieval_only or r.get("answer_passed")) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

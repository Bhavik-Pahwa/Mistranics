# Executed validation

Validation was performed on the implementation environment with Python 3.12, PostgreSQL 16.15 and Mosquitto 2.0.18. Test databases were disposable and separate from the live demonstration database.

## Test results

- Classical ML: 36 passed — original detectors/features/training tests plus unavailable-limit, inclusive-boundary, unit mismatch, finite-input, attributed runtime approval, detector independence and duplicate-evaluation regressions.
- Applied AI/integration: 28 passed against PostgreSQL — PDF/page/table text, exact version and machine/model filtering, citation/quote/numerical/safety validation, invalid LLM output, provider failure/retry, stale/disconnected telemetry, authoritative measurement summaries, feedback provenance, recovery persistence/reopening/closing, unrelated incidents, late evidence, durable lease recovery, real-time authentication/outbox, and migration upgrade preservation.
- Existing backend: 41 passed against PostgreSQL and a real MQTT broker — existing API/ingestion/decision/alert workflows, malformed/duplicate messages, reconnects, database retry, concurrent redelivery and all four migrations.
- Total: 105 passed across the three separately executed suites.
- Python compilation and Ruff undefined/unused-name checks were run. A known Starlette TestClient/httpx compatibility deprecation warning remains; tests pass.

Commands used, substituting disposable connection details:

```bash
backend/.venv/bin/python -m pytest ML/tests -q
TEST_AI_DATABASE_URL=postgresql+psycopg://user@localhost/ai_test \
  backend/.venv/bin/python -m pytest AI/tests -q
(cd backend && TEST_DATABASE_URL=postgresql+psycopg://user@localhost/backend_test \
  TEST_MQTT_PORT=1883 .venv/bin/python -m pytest tests -q)
```

The migration preservation test reconstructs migrations 001/002 with a legacy active alert, applies 003/004 twice, and verifies the original ID/status remain while incident_key defaults to __machine__.

## Live service checks

The combined Uvicorn application started from the repository-root entry point, applied migrations, connected/subscribed to MQTT and served HTTP APIs. Real MQTT telemetry passed through canonical PostgreSQL persistence and the reused manufacturer detector using an explicitly synthetic test limit configuration. The backend saved result/decision evidence, a parameter-level incident and an automatic troubleshooting session.

The live validation also observed a model attempt with an unretrieved citation; it was correctly rejected and persisted as an error. Request-scoped schema constraints and a corrective prompt with the actual validation error were added, and a subsequent live call returned the authoritative measured value with a stale-data caveat.

A real local Ollama-compatible chat model (qwen3-vl:2b-instruct, already available in the environment) returned a structured response through the application. An operator report was saved with operator_reported provenance. An independent real provider call without documentation returned an explicit insufficient-evidence response and no invented procedure.

The available server returned HTTP 501 for /api/embed with a message that embedding support must be enabled on that server. Its configuration was not changed. Real embedding retrieval is therefore not claimed as verified. Deterministic test-only embeddings/responses exercise document indexing, hybrid ranking, citations, instructions and the complete manual-to-feedback/recovery flow. Application code has no fake provider fallback.

## Limits of validation

No production manufacturer manuals, verified operating limits, approved deployment model or frontend were supplied. No real OCR extraction was run because Tesseract was unavailable; the scanned-document refusal path was tested. A deployed embedding-capable provider, corpus relevance/semantic safety evaluation, model approval/feature availability, production authentication/tenant isolation, retention/backup, integrated Docker packaging and throughput/latency guarantees remain unverified.

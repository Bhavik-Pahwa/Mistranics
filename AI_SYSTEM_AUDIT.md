# AI system audit — before implementation

The repository contains a FastAPI/PostgreSQL backend and a standalone classical ML package. No application frontend is present. Initial inspection covered backend/app, migrations, API_CONTRACT.md, all ML model/detector/preparation modules, CLI, tests, and supplied PRDs.

| Area | Existing implementation | Missing functionality / verification | Required action |
|---|---|---|---|
| Backend/API | Implemented: FastAPI factory, /api/v1 routes, three bearer-token roles | Existing tests must be rerun after extension | Mount optional AI routes into this application |
| MQTT | Implemented: one Paho subscriber, bounded queue, QoS 1 commit-before-ack and reconnect | Connection readiness is not persisted | Preserve ingestion; derive telemetry staleness from observation timestamps |
| Telemetry | Implemented: canonical PostgreSQL windows, quality flags, registry-approved conversions, event-time queries | ML package is not connected to canonical persisted records | Consume stored canonical readings without normalization duplication |
| Feature windows | Implemented: 3-second summaries, 15- and 60-second history, fixed 22-column schema | Existing extractor invents peak values from RMS and substitutes mean for missing extrema; inference accepts incomplete zero-filled rows | Preserve versioned schema and longer context, remove invented measurements, refuse incomplete inference |
| Detector A | Implemented: approved-status filtering, mode checks, statistical rules | Missing/unapproved limits incorrectly report completed; units are not compared; missing applicability context can match a limit | Fix these concrete defects; retain implementation and configuration records |
| Detector B | Implemented: Isolation Forest training/inference, artifact metadata, chronological training split | Incomplete/nonfinite features and feature-column mismatch not guarded; no production artifact approval established | Keep estimator/training/model artifacts; validate inference and never auto-train |
| Detector independence | Sequential execution in pipeline | An unexpected exception in A prevents B from executing; duplicate input emits completed empty findings | Isolate each detector; add canonical-record execution path; duplicates produce no new evaluation |
| Database | Existing assets, sensor_readings, detector_results, decisions, alerts, lifecycle events, policy versions | No processing checkpoint, normalized anomaly events, documents or conversation records | Extend shared SQLAlchemy metadata and add forward migrations; do not duplicate assets/telemetry/results |
| Incidents | Persisted alerts, acknowledgment/resolution and events are implemented | Current grouping is machine-level, no RECOVERING/CLOSED, parameter correlation, hysteresis or reopen | Extend existing alert records with a correlation key and condition metadata; preserve legacy API behavior |
| Approved limits | ML in-memory typed configuration, approval/source fields | No runtime loader from configuration; no administrative verification API | Use reviewed local configuration as authoritative source, expose read-only context; no LLM approval |
| PDF processing | Not implemented | Extraction, page/section metadata, OCR and upload missing | Add bounded PDF ingestion under AI |
| Vector database | Not implemented | Embeddings, lexical/vector ranking and exact version/applicability filtering missing | Add PostgreSQL-backed bounded vector storage and hybrid ranking; avoid new DB service |
| LLM integration | Not implemented | Provider, structured output, provenance checks, retry/failure state missing | Add isolated configurable Ollama HTTP provider; no fabricated fallback answers |
| WebSocket | Not implemented | Real-time events and durable publication missing | Add one optional authenticated socket with persisted outbox; API resync remains authoritative |
| Frontend | Not present | No components/design to integrate | Provide contracts for consumers; user scope is ML and applied AI, so add no frontend |
| Configuration/logging | Environment settings, .env example, lightweight logs | No AI/ML runtime settings | Extend existing settings; provider secrets remain environment-only |

Initial test attempt: ML tests could not collect in backend/.venv because NumPy/scikit-learn dependencies were not installed there. Existing test claims (including README's unverified 100% coverage statement) are not treated as evidence.

## Integration plan and preservation decisions

Reuse ML algorithms, fixed feature column order and the established 60-second context in addition to 3/15 seconds. A deployed model must not silently receive a different schema. Where upstream summaries lack extrema/peaks, report insufficient data instead of inventing them. Keep Joblib artifacts untouched and load only an explicitly configured trusted artifact.

Use the existing backend polling worker for optional ML execution, not another MQTT client or telemetry loop. Persist processing checkpoints and normalized findings. Extend existing alerts for parameter-level condition lifecycle while keeping acknowledgment separate. Existing decisions/evidence remain the authoritative link to alert origins. Legacy machine-level policy alert generation must not run concurrently with the new incident manager.

Keep applied AI modules in AI and classical/runtime modules in ML. Mount AI routes into the existing backend. New persistence belongs to the same database and migration sequence. AI failures must be caught independently from ML processing. Provider calls occur outside telemetry/incident transactions. Documents never populate approved limit configuration.

No provider credentials, verified production manufacturer limits, production model approval, manual PDFs, or frontend were supplied. Implement real integration boundaries and explicit unavailable states; use fakes only in tests and label synthetic fixtures.

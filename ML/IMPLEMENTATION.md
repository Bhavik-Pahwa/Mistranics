# Classical ML implementation (Part A)

## Reused implementation

The existing ML package already supplied typed telemetry/limit/result schemas, transport-independent preparation, event-time buffers, manufacturer checks, statistical rules, a fixed 22-column feature extractor, Isolation Forest inference, offline training and a CLI. These modules and the existing model artifacts were retained. The established 3-second cadence and 15-second context are preserved; the existing 60-second context remains because the model schema already uses it. No model is retrained or replaced on startup.

The inspection and defect inventory are in ../AI_SYSTEM_AUDIT.md. This document supersedes earlier implementation claims about inferred peaks, completed checks with missing limits, and unrestricted scoring of zero-filled features.

## Files

- models/: typed telemetry, manufacturer limit approval/source/applicability records, 22 ordered feature columns, detector envelopes.
- shared/: standalone telemetry validation, unit helpers and event-time history.
- detector_a/: approved manufacturer comparisons and independently callable statistical rules.
- detector_b/: feature extraction, existing Isolation Forest estimator/metadata loading, inference and explicit offline training.
- pipeline.py: standalone preparation plus evaluate_record, which consumes an already-canonical backend record without repeating backend conversions.
- persistence.py: ml_processed_windows checkpoints and normalized anomaly_events, using the backend's shared Base.
- runtime.py: the optional backend adapter, configuration loader, bounded history reconstruction, result persistence, parameter-level incident aggregation and recovery.
- examples/: illustrative incident policy and a clearly labelled synthetic limit fixture.
- tests/: original detector/training tests plus regression checks.
- INTEGRATION_CONTRACT.md and contracts/DETECTOR_CONTRACT.md: integration and standalone envelope contracts.

## Concrete fixes

Manufacturer checks now compare units, skip unsupported average/duration semantics, reject missing conditional operating context, and return insufficient_data when no applicable measurement/limit can be checked. Unapproved limits remain excluded. Exact boundaries are inclusive. Findings retain approved lower/upper values, configuration version and source references. Runtime-approved file records require reviewer and timezone-aware approved_at attribution. A reviewed configuration file is the authority; document retrieval cannot modify it.

Each detector call has an independent exception boundary. A failure produces processing_error while the remaining detectors execute. Duplicate standalone windows produce no new detector results rather than a fabricated completed/normal result. Nonfinite/non-numeric sensor values are rejected.

Feature extraction no longer estimates peak vibration from RMS or claims temperature extrema equal a mean. Explicit min_temperature, max_temperature, peak_rms and peak_vibration measurements are required. Missing entries retain tagged feature placeholders for the existing extraction contract, but inference rejects missing/incomplete/unreliable/nonfinite rows before scoring. Full 15/60-second context and gaps are checked. Feature columns and schema must match model metadata exactly. This intentionally changes old tests which accepted unavailable limit checks or scored fabricated/incomplete features.

The fixed feature schema was retained for compatibility. A machine with only temperature and RMS readings cannot supply every feature; Detector B reports insufficient_data (or model_unavailable when no model is configured). Source coverage and model validation must be completed before using an operational model. Scores are never interpreted as failure probabilities.

## Backend integration and data flow

Enable ML_ENABLED and launch the canonical repository-root backend entry point. The existing backend worker runs classical processing every three seconds. It reads at most 25 unprocessed persisted windows per tick and at most 1,000 event-time-ordered history windows per observation. It does not subscribe to MQTT or normalize canonical values again. The backend's approved conversion map and quality flags remain authoritative. load_pct is adapted to the existing ML load_percentage field.

Results are adapted to the existing protected detector envelope shape and stored through accept_result. Standalone metrics/skipped_reasons become source_metadata; configuration/model/schema versions are preserved. Stable run IDs reference the persisted reading and policy version. A transaction saves results, decision/evidence links, incident events and the processing checkpoint together. Retries after rollback do not mark a window processed. Existing standalone statistical-rule persistence remains in-memory; the default runtime has no configured statistical rules. A future persisted statistical-rule deployment needs explicit rule-state checkpointing rather than assuming in-memory persistence survives restart.

No backend API runs inference during reads. No second telemetry loop exists. The existing optional backend Decision Layer can continue storing its own versioned decisions; its legacy alert generation must be disabled while the classical incident manager owns alerts.

## Incidents and recovery

Existing alerts and alert_events are reused. Migration 003 adds incident_key with legacy default __machine__ and changes the active-incident uniqueness constraint to machine plus key. Existing rows retain their identity and data. No second incident table is created.

The new key is the exact parameter, an explicitly configured parameter group, or __multivariate__ for an unattributed Isolation Forest finding. Unrelated parameters never automatically merge. Each abnormal finding has its own anomaly_events record linked to exact detector result, incident and observation time. Repeated findings update observation count, latest detection time, detector contributions, source-category severity, and simple observed-value trend. Statistical anomaly alone is not a confirmed mechanical fault.

Condition lifecycle is stored in alert metadata as ACTIVE, RECOVERING, RESOLVED or CLOSED. Acknowledgment remains a separate timestamp and legacy alert status, so acknowledging does not imply recovery. Three consecutive reliable observations over at least six seconds are the documented prototype recovery default. Gaps greater than 4.5 seconds reset persistence; missing/failed contributing detectors or missing affected parameters cannot advance recovery. The defaults reflect the three-second cadence and are configurable, not manufacturer-approved safety rules.

Correlation defaults to 120 seconds to combine repeated observations and reopen a resolved condition during a brief recurrence. Outside that interval a prior active condition is explicitly closed with correlation_expired provenance before creating a new incident. CLOSED requires a new incident on recurrence. Late normal observations cannot resolve newer abnormal evidence. Old out-of-correlation anomalies are retained in a closed historical incident and cannot close a newer active incident. Only meaningful state changes create operator-facing outbox events; all relevant findings and recovery observations remain persisted.

Policy versions are registered immutably as classical:<version>. Changing grouping/recovery configuration requires a new version. Previously checkpointed windows are not automatically rerun when configuration changes.

## Configuration and operation

See ../AI/README.md for the combined service and ../AI/.env.example. Important fields: ML_ENABLED, ML_LIMITS_FILE, ML_MODEL_FILE and ML_INCIDENT_POLICY_FILE. Limit configuration is a JSON list of existing ManufacturerLimitRecord objects. The active file content hash identifies the evaluated configuration. Artifact files are loaded only if explicitly selected; load failures leave Detector A available and Detector B unavailable. Joblib files must be trusted because deserialization executes Python code.

For standalone use:

```bash
python -m pip install -r ML/requirements.txt
python -m pytest ML/tests -q
python -m ML.cli simulate --steps 10 --with-anomaly
```

The CLI's synthetic simulation/training is a demonstration, not an operational dataset or automatically approved model. Incomplete synthetic sensor streams now correctly leave Detector B indeterminate/unavailable instead of inventing features.

## Boundaries and limitations

Backend ingestion, identity and canonical conversions are reused unchanged. Standalone preparation remains available for offline callers; it is not another deployed ingestion service. Existing artifacts were not modified. The runtime does not supply a manufacturer review UI, automatic model training/approval, calibrated failure probabilities, waveform reconstruction, notifications, or protective shutdown. It has no guaranteed latency/safety target.

Manufacturer average/duration checks require additional valid upstream evidence and currently return an unavailable check. Reviewed machine-specific limits, applicable models, feature availability, registry mapping and production incident policy remain deployment inputs. The one configured model package is a prototype-wide selection; multi-model machine dispatch is not implemented. Run one backend process with the stable MQTT client ID.

# INDUX Machine Health Engine (ML SWE) — Implementation & Architecture Report

**Sprint Scope:** Machine Health Engine (Detector A, Detector B, Shared Telemetry Preparation)  
**Author:** ML SWE  
**Date:** 2 November 2026  
**Status:** Completed & Validated

---

## 1. Executive Summary & Scope Separation

Per the sprint objectives, the Machine Health Engine has been implemented completely in an isolated directory (`ML/`).
- **Zero modification to `backend/`:** No files within `backend/` were touched, altered, or replaced.
- **Independent architecture:** The ML package operates independently with its own data models, validation layer, detector engines, pipeline orchestrator, CLI, test suite, and contracts.
- **Contract compatibility:** The output contracts conform directly to the common detector result envelope required by the downstream Decision Layer and the backend callback endpoint (`POST /internal/detector-results`).

---

## 2. Architecture & Data Flow

```
Incoming Telemetry (3s JSON Window)
               │
               ▼
┌──────────────────────────────────────────────────┐
│      SHARED VALIDATION & PREPARATION LAYER       │
│  - Identity & schema validation                  │
│  - Timezone-aware UTC normalization              │
│  - Unit normalization (canonical units)          │
│  - Missing-value preservation (no zero-fill)    │
│  - Duplicate detection & idempotent handling     │
│  - Bounded late-arrival handling (< 15s latency) │
│  - Per-sensor quality tracking                   │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
          Validated Record + History Buffer
           (15s & 60s Sliding Windows)
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌───────────────────────┐   ┌────────────────────────────────┐
│      DETECTOR A       │   │          DETECTOR B            │
│  Manufacturer Limits  │   │      Feature Engineering       │
│           +           │   │      (22-feature vector)       │
│   Statistical Rules   │   │               +                │
│  (Mean, Std, Z-Score, │   │    Isolation Forest Scoring    │
│  Rate-of-Change,      │   │    (Unsupervised Multi-        │
│   Persistence)        │   │     variate Anomaly Detection) │
└───────────┬───────────┘   └───────────────┬────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
              Structured Detector Envelopes
            (Distinguishable, Traceable JSON)
                            │
                            ▼
            Downstream Decision Layer / Backend
```

---

## 3. Resolution of PRD Ambiguities (What We Did and Why)

Section 13.1 of the PRD outlines 10 feature and timing ambiguities that had to be resolved before freezing the implementation. Here is each decision, what was implemented, and the engineering rationale:

### 1. “Peak RMS” (Category 1)
- **The Ambiguity:** RMS is already a statistical aggregation over time; "Peak RMS" can be interpreted as either the maximum sub-window RMS or a peak-to-RMS crest factor product.
- **What We Did:** In `ML/detector_b/feature_extractor.py`, if a dedicated `peak_rms` parameter is present in the telemetry (e.g. from an edge smart sensor computing sub-second RMS windows), we use it directly. If absent, we compute it via crest-factor approximation: $\text{vibration\_rms} \times \sqrt{2} \approx 1.4142 \times \text{vibration\_rms}$.
- **Why:** Real-world industrial vibration gateways (e.g., IFM, Banner) often calculate high-frequency sub-window RMS. This approach provides an immediate fallback that preserves physical scale without crashing or zero-filling.

### 2. “Peak Vibration” (Category 1)
- **The Ambiguity:** Whether peak vibration represents raw waveform peak or precomputed amplitude.
- **What We Did:** Defined as peak amplitude within the 3-second window in canonical unit `mm/s`. If `peak_vibration` is provided in readings, it is used; otherwise estimated from RMS as $1.4142 \times \text{vibration\_rms}$.
- **Why:** Keeps velocity amplitude consistent with ISO 10816 standards for machinery vibration severity.

### 3. “Mean Output” (Category 1)
- **The Ambiguity:** "Output" is not a defined physical dimension.
- **What We Did:** Defined canonical parameter `mean_output` as machine active output power measured in kilowatts (`kW`). Supported incoming units include `kW`, `W`, `MW`, and `hp` (converted to `kW`).
- **Why:** Active electrical/mechanical power in kW correlates directly with mechanical load and operating state across motors, pumps, and compressors.

### 4. Temperature Change: Delta vs Rate/Slope (Category 2)
- **The Ambiguity:** Whether `temperature_change_15s` and `temperature_change_60s` should be simple differences or slopes.
- **What We Did:** Implemented as direct temperature difference in canonical degrees Celsius:
  $$\Delta T_{15\text{s}} = T_{\text{current}} - T_{15\text{s\_ago}}$$
  $$\Delta T_{60\text{s}} = T_{\text{current}} - T_{60\text{s\_ago}}$$
  Slopes/rates are computed separately for rate-of-change rules where time denominator is explicit.
- **Why:** A direct delta in °C maintains clear physical interpretability for human engineers and prevents unit confusion.

### 5. Pressure Rate of Change (Category 2)
- **The Ambiguity:** Requires a specified time window, calculation basis, and canonical unit.
- **What We Did:** Calculated over the short-term 15-second window and expressed in canonical units of $\text{kPa/min}$:
  $$\text{ROC}_{\text{pressure}} = \frac{P_{\text{current}} - P_{\text{oldest}}}{\Delta t / 60.0}$$
- **Why:** In fluid handling, pressure transients like hydraulic hammer or cavitation appear over short multi-second windows, and $\text{kPa/min}$ (or $\text{bar/min}$) is the standard industrial unit.

### 6. Rolling Vibration Average (Category 2)
- **The Ambiguity:** Which vibration measure to average.
- **What We Did:** Averaged the canonical `vibration_rms` across the 15s and 60s windows (`rolling_vibration_average_15s`, `rolling_vibration_average_60s`).
- **Why:** Averaging RMS vibration smooths out transient mechanical noise and captures true baseline structural vibration drift.

### 7. Rolling Current Standard Deviation (Category 2)
- **The Ambiguity:** Undefined window duration.
- **What We Did:** Implemented both `rolling_current_std_15s` and `rolling_current_std_60s`.
- **Why:** Short-term current variation (15s) indicates momentary motor electrical imbalance or phase flutter, while 60s current variation indicates sustained load fluctuations.

### 8 & 9. Operating Mode & Operating State Encoding (Category 3)
- **The Ambiguity:** Categorical strings cannot be passed directly into Scikit-learn Isolation Forest.
- **What We Did:** Built deterministic, fixed ordinal maps:
  - `OPERATING_MODE_MAP`: `{"unknown": 0, "standard": 1, "eco": 2, "high_performance": 3, "maintenance": 4}`
  - `OPERATING_STATE_MAP`: `{"unknown": -1, "idle": 0, "starting": 1, "running": 2, "stopping": 3, "fault": 4}`
- **Why:** Fixed numerical encodings guarantee that feature vectors have invariant dimensions and order between training and inference without unpredictable one-hot column expansion.

### 10. Handling Missing Optional Context (RPM, Load)
- **The Ambiguity:** Some installations do not measure RPM or load percentage.
- **What We Did:** Implemented dual-indicator representation:
  - `rpm`: 0.0 when unmeasured; actual value when present.
  - `load_percentage`: 0.0 when unmeasured; actual value when present.
  - `has_rpm`: 1.0 if measured, 0.0 if imputed.
  - `has_load`: 1.0 if measured, 0.0 if imputed.
- **Why:** This ensures the feature vector always has exactly 22 columns with fixed ordering, while informing the tree-based Isolation Forest model whether an apparent 0 RPM is an idle machine or simply an uninstrumented shaft.

---

## 4. Directory Structure & File Roles

```
ML/
├── models/
│   ├── telemetry.py            # Pydantic schemas for raw & validated telemetry, sensor readings, operating context
│   ├── limits.py               # Manufacturer limit models, verification statuses (candidate/approved), source references
│   ├── features.py             # Feature schema definitions (FEATURE_COLUMNS, 22 columns), FeatureSnapshot model
│   └── results.py              # Common DetectorResultEnvelope, Finding model, DataQualityMetadata
├── shared/
│   ├── units.py                # Normalized conversion tables (temperature, pressure, vibration, current, power, speed)
│   ├── validator.py            # Validates schema, timestamps, and sensor quality; generates ValidatedTelemetryRecord
│   └── history_buffer.py       # Time-ordered sliding window store, deduplication by (machine_id, window_id), lateness check
├── detector_a/
│   ├── limits_engine.py        # Evaluates approved manufacturer limits; ignores candidate/under_review/rejected
│   ├── statistical_engine.py   # Computes rolling mean/std, Z-score (zero-variance safe), rate of change, persistence
│   └── engine.py               # Combines A1 and A2 into a unified Detector A runner
├── detector_b/
│   ├── feature_extractor.py    # Extracts the fixed 22-column feature row from current window and historical buffers
│   ├── trainer.py              # Chronological train/val split, IsolationForest fitting, threshold selection, Joblib I/O
│   ├── inference.py            # Scores feature snapshots using loaded model, threshold comparison, structured findings
│   └── engine.py               # Combines feature extraction and inference into Detector B runner
├── contracts/
│   └── DETECTOR_CONTRACT.md    # API and envelope interface contract for backend and decision layer
├── tests/
│   ├── test_models.py
│   ├── test_shared_prep.py
│   ├── test_detector_a_limits.py
│   ├── test_detector_a_statistical.py
│   ├── test_feature_extractor.py
│   ├── test_trainer.py
│   ├── test_detector_b_inference.py
│   └── test_pipeline_integration.py
├── pipeline.py                 # End-to-end MachineHealthPipeline runner
├── cli.py                      # Training and stream simulation CLI
├── requirements.txt            # Python dependencies
└── README.md                   # Package documentation
```

---

## 5. Major Implementation Decisions & Trade-Offs

1. **In-Memory History Buffer vs External Database for 15s/60s Windows:**
   - *Decision:* Maintain an in-memory chronological buffer (`HistoryBuffer`) per machine bounded to 300 seconds.
   - *Rationale:* Telemetry arrives every 3 seconds. Querying an external database over HTTP or SQL every 3 seconds to compute rolling statistics adds unnecessary latency and network failure modes to the ML layer.
2. **Strict Approval Gate for Manufacturer Limits:**
   - *Decision:* At runtime, `ManufacturerLimitsEngine` filters strictly on `status == LimitVerificationStatus.approved`. If only `candidate` limits exist (e.g. from an unverified LLM extraction), they are ignored and recorded in `skipped_reasons`.
   - *Rationale:* Conforms directly to the safety requirement in Section 6.1: LLM-extracted limits must never trigger machine alarms without human engineering signoff.
3. **Z-Score Zero-Variance Protection:**
   - *Decision:* When the baseline or window standard deviation is near zero ($< 10^{-6}$), the engine clamps `z_score = 0.0` and logs a quality warning rather than throwing `ZeroDivisionError`.
   - *Rationale:* Industrial sensors during idle steady-state often produce constant integer readings (zero variance). Crashing or returning infinite Z-scores generates false alarms.
4. **Quantile Validation Threshold for Isolation Forest:**
   - *Decision:* Instead of relying on arbitrary default thresholds, the trainer computes `score_samples` over a held-out chronological validation set of healthy data and selects the decision threshold at the lower 2nd percentile.
   - *Rationale:* Makes the anomaly detector conservative on normal healthy baseline while remaining sensitive to true multivariate drifts.

---

## 6. How to Run & Validate

### 1. Execute Full Test Suite
```bash
python -m pytest ML/tests -v
```
All 21 unit and integration tests execute and pass in ~8 seconds.

### 2. Train an Isolation Forest Model
```bash
python -m ML.cli train --output ML/models/model_artifacts/isolation_forest.joblib --samples 300
```

### 3. Run Simulated Telemetry Pipeline
```bash
python -m ML.cli simulate --steps 8 --with-anomaly
```
Demonstrates normal operations for steps 1-5 followed by an anomalous thermal, electrical, and vibration event on steps 6-8:
- Step 6: Limits detector fires on max temperature crossing; ML Isolation Forest detects multivariate outlier; Statistical detector awaits persistence.
- Step 7: Persistence count (2 consecutive windows) is reached; Statistical rate-of-change rule fires alongside Limits and ML detectors.

---

## 7. Known Limitations & Handoff Notes

1. **Downstream Decision Policy:** Combining findings from Detector A and Detector B into an incident or alert severity is the responsibility of the Decision Layer. The Machine Health Engine outputs structured evidence only.
2. **Model Retraining:** Retraining is an offline, controlled process. Live inference never automatically updates the model estimator or adapts healthy baseline reference statistics.


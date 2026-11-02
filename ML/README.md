# INDUX Machine Health Engine (ML & Detectors)

Classical Machine Learning & Detector package for the INDUX platform, with an optional adapter to the existing backend.

This package implements **Shared Telemetry Preparation**, **Detector A** (Manufacturer Limits & Statistical Rules Engine), and **Detector B** (Feature Engineering & Isolation Forest Engine), with standalone algorithms and an optional backend integration in runtime.py and persistence.py. See IMPLEMENTATION.md for audited corrections and integration behavior.

## Directory Layout

```
ML/
├── models/                     # Strongly-typed Pydantic data schemas
│   ├── telemetry.py            # Raw & validated telemetry records, sensor readings
│   ├── limits.py               # Manufacturer limits & verification statuses
│   ├── features.py             # Feature schema (features-1.0) and column definitions
│   └── results.py              # Common detector result envelopes & structured findings
├── shared/                     # Shared telemetry processing
│   ├── units.py                # Canonical unit normalization (degC, mm/s, A, kPa, kW, rpm)
│   ├── validator.py            # Schema, identity, timestamp, and sensor-quality validation
│   └── history_buffer.py       # Time-ordered rolling buffers (15s, 60s), deduplication & lateness
├── detector_a/                 # Detector A
│   ├── limits_engine.py        # A1: Manufacturer limits checker (approved status enforcement)
│   ├── statistical_engine.py   # A2: Rolling mean/std, Z-scores, rate of change, persistence
│   └── engine.py               # Unified Detector A runner
├── detector_b/                 # Detector B
│   ├── feature_extractor.py    # B1: 22-column fixed feature snapshot extractor
│   ├── trainer.py              # B2: Chronological Isolation Forest training & Joblib persistence
│   ├── inference.py            # B3: Real-time scoring against decision threshold
│   └── engine.py               # Unified Detector B runner
├── contracts/
│   └── DETECTOR_CONTRACT.md    # Integration contract for Decision Layer and Backend API
├── tests/                      # Detector and regression test suite
│   ├── test_models.py
│   ├── test_shared_prep.py
│   ├── test_detector_a_limits.py
│   ├── test_detector_a_statistical.py
│   ├── test_feature_extractor.py
│   ├── test_trainer.py
│   ├── test_detector_b_inference.py
│   └── test_pipeline_integration.py
├── pipeline.py                 # End-to-end orchestrator combining shared prep and both detectors
├── cli.py                      # CLI for offline model training and streaming simulation
├── requirements.txt            # Pinned package dependencies
└── IMPLEMENTATION.md           # Architectural documentation and resolution of PRD ambiguities
```

## Setup & Requirements

```bash
pip install -r ML/requirements.txt
```

Core dependencies: `pydantic>=2.0.0`, `scikit-learn>=1.3.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `joblib>=1.3.0`, `pytest>=7.0.0`.

## Running Tests

Execute the full suite across all modules:

```bash
python -m pytest ML/tests -v
```

## CLI Usage

### 1. Train an Isolation Forest Model
```bash
python -m ML.cli train --output ML/models/model_artifacts/isolation_forest.joblib --samples 300
```
This trains an Isolation Forest model using a chronological train/validation split, computes the calibrated decision threshold on validation data, and persists both the `.joblib` model artifact and its `.json` metadata sidecar.

### 2. Simulate Telemetry Stream
```bash
python -m ML.cli simulate --steps 10 --with-anomaly
```
Simulates 10 steps of 3-second telemetry windows through the entire pipeline:
- Steps 1-7: normal telemetry stream (both detectors report 0 violations).
- Steps 8-10: injected thermal and electrical anomaly, triggering Detector A manufacturer limit crossing, statistical persistence deviation, and Detector B multivariate isolation forest anomaly.


## Backend integration update

Existing algorithms and artifacts were retained. Missing/inapplicable limits now report unavailable evaluation, unit mismatches are rejected, detector failures are isolated, and inference refuses incomplete/fabricated feature rows. Mean-only telemetry does not establish real extrema or vibration peaks. The existing fixed 22-column schema and 60-second context remain alongside the required 3/15-second windows.

For integrated execution, configuration and incident APIs see [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md), [IMPLEMENTATION.md](IMPLEMENTATION.md), and [../AI/README.md](../AI/README.md). Earlier simulation descriptions assume complete sensor features; sparse simulations now correctly return insufficient_data for Detector B.

# Detector B: Dual Isolation Forest Anomaly Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Detector B v2.0 (Dual Isolation Forest Anomaly Detection) supporting both Physical Hardware (DS18B20 temperature, 12 features) and Online Simulator (temperature, vibration, current, 36 features) with independent training pipelines, model artifacts, calibrated thresholds, warm-up handling, and a unified common output contract, integrating cleanly with the existing INDUX backend and Machine Health Engine architecture.

**Architecture:** 
- Source-based routing determines whether incoming telemetry is dispatched to Model 1 (Physical) or Model 2 (Simulator).
- Model 1 computes 12 features across 3s, 15s, and 60s rolling windows (mean, max, min, std of temperature).
- Model 2 computes 36 features across 3s, 15s, and 60s rolling windows (mean, max, min, std for temperature, vibration, current).
- Both models maintain independent offline dataset generation, chronological train/val/test splitting with temporal gaps, Isolation Forest estimators (`n_estimators=200`, `max_samples=256`), calibrated decision thresholds, and Joblib/JSON artifacts.
- DualIsolationForestEngine wraps both models and returns the common output contract with statuses: `NORMAL`, `ANOMALY`, `INSUFFICIENT_DATA`, `SENSOR_ERROR`, `MODEL_ERROR`.
- Existing Detector A functionality is preserved intact.

**Tech Stack:** Python 3.11, Scikit-learn, NumPy, Pandas, Pydantic v2, Joblib, Pytest.

**Spec:** `INDUX --- Detector B: Dual Isolation Forest Anomaly Detection (PRD v2.0)`

## Global Constraints
- Target code resides in `ML/detector_b/`, `ML/models/`, `ML/pipeline.py`, and `ML/cli.py`.
- Do not modify existing Detector A functionality (`ML/detector_a/`).
- Preserve existing backend functionality and database models; do not create duplicate endpoints.
- Model 1 must accept exactly 12 features; Model 2 must accept exactly 36 features in fixed, deterministic order.
- Both models require 60 seconds of history for warm-up before producing classifications; return `INSUFFICIENT_DATA` prior to 60s.
- Incomplete/missing sensors must return `SENSOR_ERROR`, missing models must return `MODEL_ERROR`.
- Common output contract format:
  `{"detector": "B", "model_type": "physical"|"simulator", "model_version": "...", "timestamp": "...", "anomaly_score": float, "decision_threshold": float, "status": "ANOMALY"|"NORMAL"|"INSUFFICIENT_DATA"|"SENSOR_ERROR"|"MODEL_ERROR", "data_source": "physical"|"simulator"}`

## Review Focus
1. Window leakage during dataset split: chronological split must include a temporal buffer (>= 60s) between train and validation partitions.
2. Incomplete feature warm-up: evaluating at < 60s must return `INSUFFICIENT_DATA`, never fabricating normal/anomaly.
3. Partial sensor loss in simulator model: if vibration or current is missing/None, must return `SENSOR_ERROR` and never pass incomplete 36-feature vector to sklearn.
4. Feature schema mismatch: physical telemetry fed to simulator model (or vice versa) must be rejected with `MODEL_ERROR` or `SENSOR_ERROR`.
5. Existing Detector A and backend regression: ensure existing test suite continues to pass 100%.

---

### Task 1: Backend Audit & Integration Architecture Contract
**Files:**
- Create: `ML/contracts/BACKEND_AUDIT_AND_INTEGRATION_PLAN.md`

- [ ] **Step 1: Document audit of existing backend telemetry ingestion, simulator, serial sensor, and detector integration.**
- [ ] **Step 2: Formalize integration contract and source selection policy.**

---

### Task 2: Detector B v2.0 Schemas & Common Output Contract
**Files:**
- Create: `ML/models/detector_b_schemas.py`
- Test: `ML/tests/test_detector_b_schemas.py`

- [ ] **Step 1: Write test for Detector B v2.0 schemas, common output contract, and feature column definitions.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Implement schemas in `ML/models/detector_b_schemas.py`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 3: Independent Feature Engineering (Physical: 12, Simulator: 36)
**Files:**
- Create: `ML/detector_b/features_physical.py`
- Create: `ML/detector_b/features_simulator.py`
- Test: `ML/tests/test_detector_b_features.py`

- [ ] **Step 1: Write tests for 12-feature physical and 36-feature simulator rolling window extractions.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Implement `features_physical.py` and `features_simulator.py`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 4: Offline Dataset Preparation & Partitioning Pipelines
**Files:**
- Create: `ML/detector_b/data_physical.py`
- Create: `ML/detector_b/data_simulator.py`
- Test: `ML/tests/test_detector_b_datasets.py`

- [ ] **Step 1: Write tests for physical and simulator dataset generation and chronological leakage-free splitting.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Implement `data_physical.py` and `data_simulator.py`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 5: Independent Training Pipelines & Calibrated Thresholds
**Files:**
- Create: `ML/detector_b/train_physical.py`
- Create: `ML/detector_b/train_simulator.py`
- Test: `ML/tests/test_detector_b_training.py`

- [ ] **Step 1: Write tests for training both models, threshold calibration, and artifact generation.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Implement training scripts, calibrate thresholds, and generate default model artifacts in `ML/models/model_artifacts/`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 6: Inference Engines & Source-Based Selection
**Files:**
- Create: `ML/detector_b/inference_physical.py`
- Create: `ML/detector_b/inference_simulator.py`
- Create: `ML/detector_b/dual_engine.py`
- Test: `ML/tests/test_detector_b_dual.py`

- [ ] **Step 1: Write tests for physical inference, simulator inference, dual engine dispatch, warm-up, and error states.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Implement inference engines and `DualIsolationForestEngine`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 7: Integration with Machine Health Pipeline & Backend Architecture
**Files:**
- Modify: `ML/detector_b/engine.py`
- Modify: `ML/pipeline.py`
- Test: `ML/tests/test_detector_b_backend_integration.py`

- [ ] **Step 1: Write tests for pipeline integration with both physical and simulator sources and common contract output.**
- [ ] **Step 2: Run test to verify it fails.**
- [ ] **Step 3: Update `ML/detector_b/engine.py` and `ML/pipeline.py`.**
- [ ] **Step 4: Run test to verify it passes.**

---

### Task 8: CLI Commands, Full Test Suite & Comprehensive Report
**Files:**
- Modify: `ML/cli.py`
- Create: `ML/DETECTOR_B_PRD_V2_IMPLEMENTATION.md`

- [ ] **Step 1: Add CLI commands for training physical and simulator models and simulating dual streams.**
- [ ] **Step 2: Execute CLI training to generate production-ready model artifacts.**
- [ ] **Step 3: Run full pytest suite across `ML/tests/` and verify 100% pass.**
- [ ] **Step 4: Write comprehensive explanatory document `ML/DETECTOR_B_PRD_V2_IMPLEMENTATION.md`.**


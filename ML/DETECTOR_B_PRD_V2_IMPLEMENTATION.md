# INDUX — Detector B: Dual Isolation Forest Anomaly Detection (PRD v2.0)
## Implementation & Architectural Handoff Report

**Product:** INDUX  
**Component:** Detector B (AI Anomaly Detection)  
**Version:** 2.0  
**Date:** 3 November 2026  
**Status:** Implemented & Verified (54/54 tests passing)

---

## 1. Overall Detector B Architecture

Detector B v2.0 implements two independent, unsupervised Isolation Forest models operating within a unified inference framework and common output contract. It accommodates two distinct operational environments:

1. **Physical Hardware:** DS18B20 1-Wire temperature sensor probe. Single sensor channel, 12 rolling statistical features.
2. **Online Simulator:** Multi-channel motor simulation. Temperature, vibration, and current sensor channels, 36 rolling statistical features.

```
                           Incoming 3-second Telemetry Window
                                          │
                                 Source Determination
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
          source == "physical"                     source in ("simulator", "simulation")
┌───────────────────────────────────────┐   ┌───────────────────────────────────────────┐
│       MODEL 1: PHYSICAL HARDWARE      │   │        MODEL 2: ONLINE SIMULATOR          │
├───────────────────────────────────────┤   ├───────────────────────────────────────────┤
│ Sensor: DS18B20 Temperature only      │   │ Sensors: Temperature, Vibration, Current  │
│ Input Unit: °C                        │   │ Input Units: °C, mm/s, A                  │
│ Rolling Windows: 3s, 15s, 60s         │   │ Rolling Windows: 3s, 15s, 60s             │
│ Statistics: Mean, Max, Min, Std       │   │ Statistics: Mean, Max, Min, Std           │
│ Feature Count: 12                     │   │ Feature Count: 36 (3 sensors × 4 stats ×3)│
│ Artifact: physical_isolation_forest   │   │ Artifact: simulator_isolation_forest      │
│ Threshold: Independently calibrated   │   │ Threshold: Independently calibrated       │
└───────────────────┬───────────────────┘   └─────────────────────┬─────────────────────┘
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           │
                                           ▼
                             Common Detector B Response
                             {"detector": "B", "model_type": ...,
                              "status": NORMAL / ANOMALY / INSUFFICIENT_DATA ...}
```

---

## 2. Feature Engineering & Schema Ordering

Both models evaluate three overlapping time windows: **3 seconds** (immediate transient), **15 seconds** (short-term behavioral shift), and **60 seconds** (sustained drift).

### Model 1 — Physical Temperature Features (12 Columns)

| Window | Columns | Description |
|---|---|---|
| **3s Window** | `temp_mean_3s`, `temp_max_3s`, `temp_min_3s`, `temp_std_3s` | Immediate temperature level & variability |
| **15s Window**| `temp_mean_15s`, `temp_max_15s`, `temp_min_15s`, `temp_std_15s` | Short-term rolling temperature trend |
| **60s Window**| `temp_mean_60s`, `temp_max_60s`, `temp_min_60s`, `temp_std_60s` | Long-term thermal equilibrium baseline |

### Model 2 — Online Simulator Features (36 Columns)

| Window | Temperature (°C) | Vibration (mm/s) | Current (A) |
|---|---|---|---|
| **3s Window** | `temp_mean_3s`, `temp_max_3s`, `temp_min_3s`, `temp_std_3s` | `vib_mean_3s`, `vib_max_3s`, `vib_min_3s`, `vib_std_3s` | `curr_mean_3s`, `curr_max_3s`, `curr_min_3s`, `curr_std_3s` |
| **15s Window**| `temp_mean_15s`, `temp_max_15s`, `temp_min_15s`, `temp_std_15s` | `vib_mean_15s`, `vib_max_15s`, `vib_min_15s`, `vib_std_15s` | `curr_mean_15s`, `curr_max_15s`, `curr_min_15s`, `curr_std_15s` |
| **60s Window**| `temp_mean_60s`, `temp_max_60s`, `temp_min_60s`, `temp_std_60s` | `vib_mean_60s`, `vib_max_60s`, `vib_min_60s`, `vib_std_60s` | `curr_mean_60s`, `curr_max_60s`, `curr_min_60s`, `curr_std_60s` |

---

## 3. Training & Validation Pipelines

Training takes place completely offline. In accordance with PRD Section 6.5 & 7.5:
- **Primary Training Population:** Exclusively normal operating conditions (steady-state and expected variations under normal machine load).
- **Validation & Test Populations:** Held-out normal operation plus deliberately induced abnormalities (thermal runaway, mechanical unbalance, bearing faults).
- **Temporal Gap:** To prevent rolling-window feature leakage between splits, chronological partitioning enforces an explicit temporal buffer ($\ge 60$s) between Train, Validation, and Test partitions.
- **Threshold Calibration:** Scikit-learn's `score_samples()` produces lower (more negative) values for unusual points. Operational thresholds are calibrated on held-out validation data by optimizing F1-score while bounding false-positive rate ($\text{FPR} \le 8\%$).

### Model Configurations

| Hyperparameter | Value |
|---|---|
| Algorithm | Isolation Forest (`sklearn.ensemble.IsolationForest`) |
| `n_estimators` | 200 |
| `max_samples` | 256 (or `len(X_train)` if smaller) |
| `max_features` | 1.0 |
| `contamination` | `"auto"` |
| `random_state` | 42 |
| `n_jobs` | -1 |

---

## 4. Model Artifact Locations

Model artifacts are persisted via Joblib with an accompanying JSON metadata sidecar:

1. **Physical Model:**
   - Estimator: `ML/models/model_artifacts/physical_isolation_forest.joblib`
   - Metadata: `ML/models/model_artifacts/physical_isolation_forest.json`
   - Feature Schema Version: `physical-features-12`
   - Calibrated Decision Threshold: `-0.67136`
2. **Simulator Model:**
   - Estimator: `ML/models/model_artifacts/simulator_isolation_forest.joblib`
   - Metadata: `ML/models/model_artifacts/simulator_isolation_forest.json`
   - Feature Schema Version: `simulator-features-36`
   - Calibrated Decision Threshold: `-0.64107`

---

## 5. Common Output Contract (PRD Section 9.3)

Both models return a consistent response structure:

```json
{
  "detector": "B",
  "model_type": "physical",
  "model_version": "physical-iso-v2.0",
  "timestamp": "2026-11-03T10:30:00Z",
  "anomaly_score": -0.7102,
  "decision_threshold": -0.6714,
  "status": "ANOMALY",
  "data_source": "physical"
}
```

### Supported Status Enums

- `NORMAL`: Observation evaluated successfully and scored above the decision threshold.
- `ANOMALY`: Observation evaluated successfully and scored at or below the decision threshold ($\text{score} \le \text{threshold}$).
- `INSUFFICIENT_DATA`: Accumulating historical telemetry during initial warm-up ($< 60$s of history). Incomplete feature vectors are never evaluated as normal or anomaly.
- `SENSOR_ERROR`: Missing sensor stream (e.g., missing vibration for simulator model), or reading outside physical sensor range (e.g. temperature $< -55^\circ\text{C}$ or $> 125^\circ\text{C}$).
- `MODEL_ERROR`: Model artifact missing, incompatible schema version, or unhandled runtime scoring exception.

---

## 6. Offline Training & Simulation Commands

### 1. Train Model 1 (Physical Hardware DS18B20)
```bash
python -m ML.cli train-physical --output ML/models/model_artifacts/physical_isolation_forest.joblib --steps 200
```

### 2. Train Model 2 (Online Motor Simulator)
```bash
python -m ML.cli train-simulator --output ML/models/model_artifacts/simulator_isolation_forest.joblib --steps 250
```

### 3. Run Simulated Dual Telemetry Stream
```bash
python -m ML.cli simulate-dual --steps 25 --with-anomaly
```
Demonstrates 60s warm-up (`INSUFFICIENT_DATA` for steps 1–19), followed by steady-state `NORMAL` operation, followed by an induced thermal and vibration anomaly on step 23 (`ANOMALY`).

---

## 7. Verification & Test Evidence

All 54 tests across Detector A, Detector B, shared prep, and integration pass:

```bash
python -m pytest ML/tests -v
```
**Result:** `54 passed in 7.03s` (100% pass rate).


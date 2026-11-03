# Backend Audit & Integration Architecture Plan: Detector B (Dual Isolation Forest)

**Module:** Machine Health Engine — Detector B (AI Anomaly Detection)  
**Version:** 2.0  
**Date:** 3 November 2026  
**Status:** Approved for Implementation

---

## 1. Existing System Audit

### 1.1 Telemetry Ingestion Mechanisms
- **Ingestion Path:** The INDUX backend ingests 3-second telemetry windows through an MQTT subscriber configured in `backend/app/mqtt.py` and processed by `backend/app/telemetry.py` (`TelemetryState.consume`).
- **Database Telemetry:** In PostgreSQL environments, validated telemetry rows are stored in the `sensor_readings` table (`Reading` model in `backend/app/db.py`).
- **Buffer & Deduplication:** `TelemetryState` tracks sequences by `(source, device_id)` and rejects out-of-order or duplicate sequence numbers. Windows are bounded to exactly 3.0 seconds ($\pm 0.01$s).

### 1.2 Telemetry Sources
1. **Physical Hardware:**
   - **Origin:** ESP32 / Arduino reading a DS18B20 1-Wire temperature probe via USB serial at 9600 baud (`backend/examples/serial_sensor.py`).
   - **Payload Schema:** `source: "physical"`. Contains `temperature: {mean, min, max, unit: "degC", sample_count, status: "valid"}`. Range is physical probe bounds $[-55^\circ\text{C}, 125^\circ\text{C}]$.
   - **Vibration & Current:** Not physically wired to this probe; physical telemetry contains temperature only.
2. **Online Simulator:**
   - **Origin:** Real-time motor simulator (`backend/app/simulator.py` & `backend/examples/iot_simulator.py`).
   - **Payload Schema:** `source: "simulation"` or `"simulator"`.
   - **Sensor Channels:**
     - Motor Temperature ($^\circ\text{C}$): Ambient 26–28°C base, rising with RPM and failure modes up to 100°C+.
     - Motor Vibration ($\text{mm/s}$ RMS & 3-axis accelerometer/gyroscope): Residual unbalance at shaft frequency, 2x harmonics for misalignment, bearing impulse ring-downs, or loose mount rattles.
     - Motor Current ($\text{A}$): Baseline 10–12A, scaling with speed and mechanical load up to 25–35A.

### 1.3 Existing Detector Integrations
- **Detector A (Manufacturer Limits & Statistical Rules Engine):** Located in `ML/detector_a/`. Evaluates approved manufacturer limits (`status == "approved"`) and rolling statistical deviation rules (mean, std, Z-score, rate-of-change, persistence). **Detector A remains completely unaffected by this implementation.**
- **Existing Detector B:** Previously implemented as a single prototype model. Detector B v2.0 replaces this with two independently trained Isolation Forest models tailored to the respective data sources.

---

## 2. Dual Isolation Forest Architecture

```
                    ┌────────────────────────────┐
                    │ Incoming 3-second Telemetry│
                    └─────────────┬──────────────┘
                                  │
                       Source Inspection
                                  │
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
   source == "physical"                     source in ("simulator", "simulation")
┌───────────────────────────────┐          ┌───────────────────────────────────┐
│     Model 1: Physical DS18B20 │          │   Model 2: Online Simulator       │
├───────────────────────────────┤          ├───────────────────────────────────┤
│ Input: Temperature only       │          │ Inputs: Temp, Vibration, Current  │
│ Windows: 3s, 15s, 60s         │          │ Windows: 3s, 15s, 60s             │
│ Features: 4 stats × 3 windows │          │ Features: 3 sensors × 4 stats × 3 │
│ Total Features: 12            │          │ Total Features: 36                │
│ Model: physical_iso_forest    │          │ Model: simulator_iso_forest       │
│ Artifact: physical_iso.joblib │          │ Artifact: simulator_iso.joblib    │
│ Threshold: Independently fit  │          │ Threshold: Independently fit      │
└───────────────┬───────────────┘          └─────────────────┬─────────────────┘
                │                                            │
                └─────────────────────┬──────────────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ Common Detector B Contract│
                        │ status: NORMAL / ANOMALY  │
                        │ / INSUFFICIENT_DATA / etc │
                        └───────────────────────────┘
```

---

## 3. Data Contract Specification

Both models output the standard response structure:

```json
{
  "detector": "B",
  "model_type": "physical",
  "model_version": "1.0",
  "timestamp": "2026-11-03T10:30:00Z",
  "anomaly_score": -0.1502,
  "decision_threshold": -0.1050,
  "status": "ANOMALY",
  "data_source": "physical"
}
```

### Status Definitions:
- `NORMAL`: Observation scored above the calibrated threshold (normal operating behavior).
- `ANOMALY`: Observation scored strictly below the calibrated threshold ($< \text{threshold}$).
- `INSUFFICIENT_DATA`: Less than 60 seconds of historical telemetry accumulated (warm-up incomplete).
- `SENSOR_ERROR`: Missing or invalid sensor readings required by the model (e.g., missing vibration for simulator model).
- `MODEL_ERROR`: Model artifact unavailable or scoring exception.


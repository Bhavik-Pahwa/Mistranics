# Machine Health Engine — Detector Integration Contract v1.0

This contract specifies the structured output interface produced by the Machine Health Engine (Detector A and Detector B) for consumption by the downstream Decision Layer and Backend API (`POST /internal/detector-results`).

## 1. Common Detector Result Envelope

Each detector evaluation returns a JSON-serializable envelope conforming to this standard structure:

```json
{
  "schema_version": "1.0",
  "detector": "manufacturer_limits | statistical | isolation_forest",
  "machine_id": "string (e.g. motor_001)",
  "window_id": "string (e.g. win-001)",
  "run_id": "string (unique run identifier, e.g. run-iso-1234abcd)",
  "evaluated_at": "ISO 8601 UTC timestamp (e.g. 2026-11-02T12:00:03Z)",
  "status": "completed | insufficient_data | invalid_input | model_unavailable | processing_error",
  "findings": [
    {
      "finding_id": "string",
      "rule_id": "string",
      "parameter": "string (optional)",
      "sensor_id": "string (optional)",
      "kind": "machine_condition | data_quality",
      "observed_value": 82.0,
      "threshold": 75.0,
      "direction": "upper | lower | deviation | anomaly",
      "unit": "degC | mm/s | A | kPa | kW | anomaly_score",
      "limit_category": "operating_range | warning | protective_trip | statistical_deviation | ml_multivariate_outlier",
      "evidence_time": "ISO 8601 UTC timestamp",
      "source_reference": {
        "document": "OEM_Manual.pdf",
        "revision": "1.2",
        "page_or_section": "Table 4-1"
      },
      "details": {}
    }
  ],
  "data_quality": {
    "status": "valid | missing | out_of_range | suspect",
    "warnings": []
  },
  "model_or_config_version": "string (e.g. iso-v1.0 or limits-v1.0)",
  "model_version": "string (required for Detector B, null for Detector A)",
  "feature_schema_version": "string (required for Detector B, e.g. features-1.0)",
  "config_version": "string (required for Detector A)",
  "metrics": {},
  "skipped_reasons": []
}
```

## 2. Evaluation Status Codes

- `completed`: Evaluation executed successfully. Findings may be empty if no violation/anomaly occurred.
- `insufficient_data`: Insufficient historical observations in the rolling window (e.g. < 3 samples in 15s or < 10 samples in 60s).
- `invalid_input`: Malformed or incompatible telemetry schema or missing required machine identity.
- `model_unavailable`: No trained, approved Isolation Forest model package is loaded.
- `processing_error`: Unexpected runtime error during scoring or calculation.

## 3. Sub-Detector Findings Contracts

### 3.1 Detector A1 — Manufacturer Limits (`detector: "manufacturer_limits"`)
- `status` only evaluates limits where `verification_status == "approved"`.
- `rule_id`: Identifier of the approved manufacturer limit.
- `observed_value`: Validated normalized measurement.
- `threshold`: Upper or lower limit configured.
- `direction`: `"upper"` or `"lower"`.
- `details.excess` / `details.shortfall`: Numerical difference from threshold.
- `source_reference`: Provenance documentation (document name, revision, page/section).

### 3.2 Detector A2 — Statistical Engine (`detector: "statistical"`)
- `rule_id`: Configured statistical rule identifier.
- `kind`: `"machine_condition"`.
- `observed_value`: Current normalized sensor measurement.
- `threshold`: Configured Z-score, rate of change, or rolling deviation threshold.
- `direction`: `"deviation"`.
- `details.persistence_count`: Consecutive violation count observed.
- `details.required_persistence`: Minimum consecutive violations before alarm.
- Zero-variance protection: When parameter standard deviation is < 1e-6, `z_score` is safely clamped to 0.0 with warning `"near-zero variance detected"` to avoid division by zero.

### 3.3 Detector B — Isolation Forest Engine (`detector: "isolation_forest"`)
- `model_version`: Identifier of the loaded Joblib model package.
- `feature_schema_version`: `"features-1.0"`.
- `metrics.anomaly_score`: Result of `model.score_samples(X)[0]`.
- `metrics.decision_threshold`: Quantile-calibrated decision threshold.
- `metrics.is_anomaly`: Boolean (`score < decision_threshold`).
- If anomalous: emits a finding with `rule_id: "isolation_forest_anomaly"`, `direction: "anomaly"`.

## 4. Feature Schema Dictionary (`features-1.0`)

Detector B converts validated 3-second telemetry windows into a fixed, ordered numerical vector of exactly 22 columns:

| Index | Column Name | Source & Window | Unit | Handling of Missing Data |
|---|---|---|---|---|
| 0 | `mean_temperature` | Direct (current 3s window) | `degC` | Preserved missing / flagged |
| 1 | `min_temperature` | Direct (current 3s window) | `degC` | Preserved missing / flagged |
| 2 | `max_temperature` | Direct (current 3s window) | `degC` | Preserved missing / flagged |
| 3 | `mean_current` | Direct (current 3s window) | `A` | Preserved missing / flagged |
| 4 | `vibration_rms` | Direct (current 3s window) | `mm/s` | Preserved missing / flagged |
| 5 | `peak_rms` | Direct / sub-window RMS max | `mm/s` | Estimated from RMS if absent |
| 6 | `peak_vibration` | Direct peak amplitude | `mm/s` | Estimated from RMS if absent |
| 7 | `mean_pressure` | Direct (current 3s window) | `kPa` | Preserved missing / flagged |
| 8 | `mean_output` | Direct machine power output | `kW` | Defaults to 0.0 |
| 9 | `temperature_change_15s` | Delta over 15s history | `degC` | 0.0 if insufficient history |
| 10 | `temperature_change_60s` | Delta over 60s history | `degC` | 0.0 if insufficient history |
| 11 | `rolling_vibration_average_15s` | Mean over 15s history | `mm/s` | Current window value fallback |
| 12 | `rolling_vibration_average_60s` | Mean over 60s history | `mm/s` | Current window value fallback |
| 13 | `rolling_current_std_15s` | Std over 15s history | `A` | 0.0 if insufficient history |
| 14 | `rolling_current_std_60s` | Std over 60s history | `A` | 0.0 if insufficient history |
| 15 | `pressure_rate_of_change` | Rate over 15s `(ΔP / Δt)` | `kPa/min` | 0.0 if insufficient history |
| 16 | `rpm` | Operating context RPM | `rpm` | Imputed 0.0 if absent |
| 17 | `load_percentage` | Operating context load | `%` | Imputed 0.0 if absent |
| 18 | `operating_mode_code` | Categorical context code | integer | unknown=0, standard=1, eco=2, high_perf=3 |
| 19 | `operating_state_code` | Categorical state code | integer | unknown=-1, idle=0, starting=1, running=2, stopping=3 |
| 20 | `has_rpm` | Presence indicator | `0.0 or 1.0` | 1.0 if observed, 0.0 if imputed |
| 21 | `has_load` | Presence indicator | `0.0 or 1.0` | 1.0 if observed, 0.0 if imputed |


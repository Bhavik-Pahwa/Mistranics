import uuid
import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional
from ML.models.telemetry import ValidatedTelemetryRecord, ReadingQuality
from ML.models.features import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    OPERATING_MODE_MAP,
    OPERATING_STATE_MAP,
    FeatureSnapshot,
)
from ML.shared.history_buffer import HistoryBuffer


class FeatureExtractor:
    """
    Detector B1: Feature Engineering Pipeline.
    Constructs a fixed, ordered numerical feature row per 3-second window
    across direct, time-based, and operating-context features.
    """

    def __init__(self, schema_version: str = FEATURE_SCHEMA_VERSION):
        self.schema_version = schema_version

    def _get_param_val(self, record: ValidatedTelemetryRecord, aliases: List[str]) -> Optional[float]:
        for alias in aliases:
            reading = record.get_reading(alias)
            if reading and reading.quality == ReadingQuality.valid and reading.value_normalized is not None:
                return reading.value_normalized
        return None

    def extract(self, current_record: ValidatedTelemetryRecord, history_buffer: HistoryBuffer) -> FeatureSnapshot:
        snapshot_id = f"feat-{uuid.uuid4().hex[:8]}"
        features: Dict[str, float] = {}
        missing_features: List[str] = []
        insufficient_history: List[str] = []

        # ----------------------------------------------------
        # Category 1: Direct Features (3s Window)
        # ----------------------------------------------------
        temp_val = self._get_param_val(current_record, ["mean_temperature", "motor_temperature", "temperature", "bearing_temperature"])
        if temp_val is not None:
            features["mean_temperature"] = float(temp_val)
            features["min_temperature"] = self._get_param_val(current_record, ["min_temperature"]) or 0.0
            if self._get_param_val(current_record, ["min_temperature"]) is None:
                missing_features.append("min_temperature")
            features["max_temperature"] = self._get_param_val(current_record, ["max_temperature"]) or 0.0
            if self._get_param_val(current_record, ["max_temperature"]) is None:
                missing_features.append("max_temperature")
        else:
            features["mean_temperature"] = 0.0
            features["min_temperature"] = 0.0
            features["max_temperature"] = 0.0
            missing_features.extend(["mean_temperature", "min_temperature", "max_temperature"])

        curr_val = self._get_param_val(current_record, ["mean_current", "current", "motor_current"])
        if curr_val is not None:
            features["mean_current"] = float(curr_val)
        else:
            features["mean_current"] = 0.0
            missing_features.append("mean_current")

        vib_val = self._get_param_val(current_record, ["vibration_velocity_rms", "vibration_rms", "vibration"])
        if vib_val is not None:
            features["vibration_rms"] = float(vib_val)
        else:
            features["vibration_rms"] = 0.0
            missing_features.append("vibration_rms")

        # Resolving ambiguity: Peak RMS and Peak vibration
        peak_rms_val = self._get_param_val(current_record, ["peak_rms"])
        if peak_rms_val is not None:
            features["peak_rms"] = float(peak_rms_val)
        else:
            features["peak_rms"] = 0.0
            missing_features.append("peak_rms")

        peak_vib_val = self._get_param_val(current_record, ["peak_vibration"])
        if peak_vib_val is not None:
            features["peak_vibration"] = float(peak_vib_val)
        else:
            features["peak_vibration"] = 0.0
            missing_features.append("peak_vibration")

        press_val = self._get_param_val(current_record, ["mean_pressure", "pressure", "discharge_pressure"])
        if press_val is not None:
            features["mean_pressure"] = float(press_val)
        else:
            features["mean_pressure"] = 0.0
            missing_features.append("mean_pressure")

        output_val = self._get_param_val(current_record, ["mean_output", "output", "power", "output_power"])
        if output_val is not None:
            features["mean_output"] = float(output_val)
        else:
            features["mean_output"] = 0.0
            missing_features.append("mean_output")

        # ----------------------------------------------------
        # Category 2: Time-based Features (15s and 60s Windows)
        # ----------------------------------------------------
        history_15s = history_buffer.get_recent_history(
            current_record.machine_id, seconds=15.0, as_of=current_record.measured_at
        )
        history_60s = history_buffer.get_recent_history(
            current_record.machine_id, seconds=60.0, as_of=current_record.measured_at
        )

        for duration, history in [(15, history_15s), (60, history_60s)]:
            if not history or (current_record.measured_at - history[0].measured_at).total_seconds() < duration:
                insufficient_history.append(f"coverage_{duration}s")
            if any((b.measured_at-a.measured_at).total_seconds() > 3.1 for a,b in zip(history, history[1:])):
                insufficient_history.append(f"gaps_{duration}s")

        # 15s Temperature delta
        if len(history_15s) >= 2 and temp_val is not None:
            oldest_temp = self._get_param_val(history_15s[0], ["mean_temperature", "motor_temperature", "temperature", "bearing_temperature"])
            features["temperature_change_15s"] = float(temp_val - oldest_temp) if oldest_temp is not None else 0.0
        else:
            features["temperature_change_15s"] = 0.0
            if len(history_15s) < 2:
                insufficient_history.append("temperature_change_15s")

        # 60s Temperature delta
        if len(history_60s) >= 2 and temp_val is not None:
            oldest_temp_60 = self._get_param_val(history_60s[0], ["mean_temperature", "motor_temperature", "temperature", "bearing_temperature"])
            features["temperature_change_60s"] = float(temp_val - oldest_temp_60) if oldest_temp_60 is not None else 0.0
        else:
            features["temperature_change_60s"] = 0.0
            if len(history_60s) < 2:
                insufficient_history.append("temperature_change_60s")

        # Rolling vibration average (15s & 60s)
        vibs_15s = [
            self._get_param_val(r, ["vibration_velocity_rms", "vibration_rms", "vibration"])
            for r in history_15s
            if self._get_param_val(r, ["vibration_velocity_rms", "vibration_rms", "vibration"]) is not None
        ]
        features["rolling_vibration_average_15s"] = float(np.mean(vibs_15s)) if vibs_15s else float(features["vibration_rms"])

        vibs_60s = [
            self._get_param_val(r, ["vibration_velocity_rms", "vibration_rms", "vibration"])
            for r in history_60s
            if self._get_param_val(r, ["vibration_velocity_rms", "vibration_rms", "vibration"]) is not None
        ]
        features["rolling_vibration_average_60s"] = float(np.mean(vibs_60s)) if vibs_60s else float(features["vibration_rms"])

        # Rolling current std (15s & 60s)
        currs_15s = [
            self._get_param_val(r, ["mean_current", "current", "motor_current"])
            for r in history_15s
            if self._get_param_val(r, ["mean_current", "current", "motor_current"]) is not None
        ]
        features["rolling_current_std_15s"] = float(np.std(currs_15s)) if len(currs_15s) >= 2 else 0.0

        currs_60s = [
            self._get_param_val(r, ["mean_current", "current", "motor_current"])
            for r in history_60s
            if self._get_param_val(r, ["mean_current", "current", "motor_current"]) is not None
        ]
        features["rolling_current_std_60s"] = float(np.std(currs_60s)) if len(currs_60s) >= 2 else 0.0

        # Pressure rate of change (kPa/min over 15s)
        if len(history_15s) >= 2 and press_val is not None:
            oldest_press = self._get_param_val(history_15s[0], ["mean_pressure", "pressure", "discharge_pressure"])
            elapsed_sec = max(1.0, (history_15s[-1].measured_at - history_15s[0].measured_at).total_seconds())
            if oldest_press is not None:
                features["pressure_rate_of_change"] = float((press_val - oldest_press) / (elapsed_sec / 60.0))
            else:
                features["pressure_rate_of_change"] = 0.0
        else:
            features["pressure_rate_of_change"] = 0.0

        # ----------------------------------------------------
        # Category 3: Operating Context Features
        # ----------------------------------------------------
        ctx = current_record.operating_context
        if ctx.rpm is not None:
            features["rpm"] = float(ctx.rpm)
            features["has_rpm"] = 1.0
        else:
            features["rpm"] = 0.0
            features["has_rpm"] = 0.0

        if ctx.load_percentage is not None:
            features["load_percentage"] = float(ctx.load_percentage)
            features["has_load"] = 1.0
        else:
            features["load_percentage"] = 0.0
            features["has_load"] = 0.0

        # Encoded categorical context
        mode_str = (ctx.operating_mode or "unknown").lower()
        features["operating_mode_code"] = float(OPERATING_MODE_MAP.get(mode_str, 0))

        state_str = (ctx.operating_state or "unknown").lower()
        features["operating_state_code"] = float(OPERATING_STATE_MAP.get(state_str, -1))

        quality = ReadingQuality.suspect if (missing_features or insufficient_history) else ReadingQuality.valid

        return FeatureSnapshot(
            snapshot_id=snapshot_id,
            machine_id=current_record.machine_id,
            feature_timestamp=current_record.measured_at,
            source_window_start=current_record.window_start,
            source_window_end=current_record.window_end,
            feature_schema_version=self.schema_version,
            features=features,
            quality_status=quality,
            missing_features=missing_features,
            insufficient_history=insufficient_history,
        )


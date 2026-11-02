import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from ML.models.telemetry import ValidatedTelemetryRecord, ReadingQuality
from ML.models.results import (
    DetectorType,
    EvaluationStatus,
    DetectorResultEnvelope,
    Finding,
    FindingKind,
    DataQualityMetadata,
)
from ML.shared.history_buffer import HistoryBuffer


class StatisticalRuleConfig(BaseModel):
    rule_id: str
    parameter: str
    sensor_id: Optional[str] = None
    reference_mean: Optional[float] = None
    reference_std: Optional[float] = None
    z_score_threshold: Optional[float] = None
    rate_of_change_threshold: Optional[float] = None  # in canonical units per min (e.g. °C/min)
    rolling_mean_threshold: Optional[float] = None
    rolling_std_threshold: Optional[float] = None
    persistence_count: int = 1
    config_version: str = "stat-rules-1.0"


class StatisticalEngine:
    """
    Detector A2: Computes rolling window statistics (15s and 60s), Z-scores against reference baselines,
    rate of change, and evaluates persistence conditions.
    """

    def __init__(self, config_version: str = "stat-rules-1.0", min_samples_15s: int = 3, min_samples_60s: int = 10):
        self.config_version = config_version
        self.min_samples_15s = min_samples_15s
        self.min_samples_60s = min_samples_60s
        self._rules: Dict[str, StatisticalRuleConfig] = {}
        # (machine_id, rule_id) -> int (consecutive violation count)
        self._persistence_state: Dict[Tuple[str, str], int] = {}

    def add_rule(self, rule: StatisticalRuleConfig) -> None:
        self._rules[rule.rule_id] = rule

    def load_rules(self, rules: List[StatisticalRuleConfig]) -> None:
        for r in rules:
            self._rules[r.rule_id] = r

    def evaluate(
        self,
        record: ValidatedTelemetryRecord,
        history_buffer: HistoryBuffer,
        run_id: Optional[str] = None,
    ) -> DetectorResultEnvelope:
        eval_run_id = run_id or f"run-stat-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        findings: List[Finding] = []
        warnings: List[str] = list(record.quality_warnings)
        metrics_computed: Dict[str, Dict[str, float]] = {}

        # 1. Fetch 15s history
        history_15s = history_buffer.get_recent_history(
            record.machine_id, seconds=15.0, as_of=record.measured_at
        )

        if len(history_15s) < self.min_samples_15s:
            return DetectorResultEnvelope(
                schema_version="1.0",
                detector=DetectorType.statistical,
                machine_id=record.machine_id,
                window_id=record.window_id,
                run_id=eval_run_id,
                evaluated_at=now,
                status=EvaluationStatus.insufficient_data,
                findings=[],
                data_quality=DataQualityMetadata(
                    status=ReadingQuality.missing,
                    warnings=[f"Insufficient 15s history: got {len(history_15s)} observations, required {self.min_samples_15s}"],
                ),
                model_or_config_version=self.config_version,
                config_version=self.config_version,
                skipped_reasons=[f"Required at least {self.min_samples_15s} historical records in 15s window"],
            )

        # 2. Fetch 60s history
        history_60s = history_buffer.get_recent_history(
            record.machine_id, seconds=60.0, as_of=record.measured_at
        )

        # 3. Calculate metrics per parameter
        for reading in record.readings:
            if reading.quality != ReadingQuality.valid or reading.value_normalized is None:
                continue

            param = reading.parameter

            # Extract valid values from 15s history
            vals_15s = [
                r.get_reading(param).value_normalized
                for r in history_15s
                if r.get_reading(param) and r.get_reading(param).quality == ReadingQuality.valid and r.get_reading(param).value_normalized is not None
            ]

            if len(vals_15s) < self.min_samples_15s:
                continue

            mean_15s = float(np.mean(vals_15s))
            std_15s = float(np.std(vals_15s))

            # Rate of change over 15s (delta / elapsed minutes)
            elapsed_sec = max(1.0, (history_15s[-1].measured_at - history_15s[0].measured_at).total_seconds())
            rate_of_change_15s = ((vals_15s[-1] - vals_15s[0]) / (elapsed_sec / 60.0))

            param_metrics = {
                "rolling_mean_15s": mean_15s,
                "rolling_std_15s": std_15s,
                "rate_of_change_15s": rate_of_change_15s,
                "valid_samples_15s": len(vals_15s),
            }

            # 60s metrics if enough samples
            vals_60s = [
                r.get_reading(param).value_normalized
                for r in history_60s
                if r.get_reading(param) and r.get_reading(param).quality == ReadingQuality.valid and r.get_reading(param).value_normalized is not None
            ]
            if len(vals_60s) >= self.min_samples_60s:
                param_metrics["rolling_mean_60s"] = float(np.mean(vals_60s))
                param_metrics["rolling_std_60s"] = float(np.std(vals_60s))
                param_metrics["valid_samples_60s"] = len(vals_60s)

            metrics_computed[param] = param_metrics

            # 4. Check rules matching this parameter
            matching_rules = [
                r for r in self._rules.values()
                if r.parameter.lower() == param.lower()
                and (r.sensor_id is None or r.sensor_id == reading.sensor_id)
            ]

            for rule in matching_rules:
                state_key = (record.machine_id, rule.rule_id)
                rule_violated = False
                violation_details = {}

                # Z-Score check
                if rule.z_score_threshold is not None:
                    ref_mean = rule.reference_mean if rule.reference_mean is not None else mean_15s
                    ref_std = rule.reference_std if rule.reference_std is not None else std_15s

                    # Zero or near-zero variance protection (Review Focus 1)
                    if ref_std < 1e-6:
                        z_score = 0.0
                        warnings.append(
                            f"Rule {rule.rule_id}: near-zero standard deviation ({ref_std}) for {param}; division avoided."
                        )
                    else:
                        z_score = abs(reading.value_normalized - ref_mean) / ref_std

                    param_metrics["z_score"] = z_score

                    if z_score > rule.z_score_threshold:
                        rule_violated = True
                        violation_details["z_score"] = z_score
                        violation_details["threshold"] = rule.z_score_threshold

                # Rate of change check
                if rule.rate_of_change_threshold is not None:
                    if abs(rate_of_change_15s) > rule.rate_of_change_threshold:
                        rule_violated = True
                        violation_details["rate_of_change"] = rate_of_change_15s
                        violation_details["threshold"] = rule.rate_of_change_threshold

                # Rolling std check
                if rule.rolling_std_threshold is not None and std_15s > rule.rolling_std_threshold:
                    rule_violated = True
                    violation_details["rolling_std"] = std_15s
                    violation_details["threshold"] = rule.rolling_std_threshold

                # Persistence handling
                if rule_violated:
                    curr_count = self._persistence_state.get(state_key, 0) + 1
                    self._persistence_state[state_key] = curr_count

                    if curr_count >= rule.persistence_count:
                        findings.append(
                            Finding(
                                finding_id=f"f-stat-{uuid.uuid4().hex[:8]}",
                                rule_id=rule.rule_id,
                                parameter=param,
                                sensor_id=reading.sensor_id,
                                kind=FindingKind.machine_condition,
                                observed_value=reading.value_normalized,
                                threshold=rule.z_score_threshold or rule.rate_of_change_threshold or rule.rolling_std_threshold,
                                direction="deviation",
                                unit=reading.unit_normalized or reading.unit_original,
                                limit_category="statistical_deviation",
                                evidence_time=record.measured_at,
                                details={
                                    "persistence_count": curr_count,
                                    "required_persistence": rule.persistence_count,
                                    **violation_details,
                                },
                            )
                        )
                else:
                    # Reset persistence count when condition clears
                    self._persistence_state[state_key] = 0

        overall_quality = ReadingQuality.suspect if warnings else ReadingQuality.valid

        return DetectorResultEnvelope(
            schema_version="1.0",
            detector=DetectorType.statistical,
            machine_id=record.machine_id,
            window_id=record.window_id,
            run_id=eval_run_id,
            evaluated_at=now,
            status=EvaluationStatus.completed,
            findings=findings,
            data_quality=DataQualityMetadata(status=overall_quality, warnings=warnings),
            model_or_config_version=self.config_version,
            config_version=self.config_version,
            metrics=metrics_computed,
            skipped_reasons=[],
        )


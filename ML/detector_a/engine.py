from typing import Optional, Tuple
from ML.models.telemetry import ValidatedTelemetryRecord
from ML.models.results import DetectorResultEnvelope
from ML.shared.history_buffer import HistoryBuffer
from ML.detector_a.limits_engine import ManufacturerLimitsEngine
from ML.detector_a.statistical_engine import StatisticalEngine


class DetectorA:
    """
    Detector A Engine: Encapsulates both Manufacturer Limits checks (A1)
    and Statistical deviation checks (A2).
    """

    def __init__(
        self,
        limits_engine: Optional[ManufacturerLimitsEngine] = None,
        statistical_engine: Optional[StatisticalEngine] = None,
    ):
        self.limits_engine = limits_engine or ManufacturerLimitsEngine()
        self.statistical_engine = statistical_engine or StatisticalEngine()

    def evaluate_limits(
        self, record: ValidatedTelemetryRecord, run_id: Optional[str] = None
    ) -> DetectorResultEnvelope:
        return self.limits_engine.evaluate(record, run_id=run_id)

    def evaluate_statistical(
        self,
        record: ValidatedTelemetryRecord,
        history_buffer: HistoryBuffer,
        run_id: Optional[str] = None,
    ) -> DetectorResultEnvelope:
        return self.statistical_engine.evaluate(record, history_buffer, run_id=run_id)

    def evaluate(
        self,
        record: ValidatedTelemetryRecord,
        history_buffer: HistoryBuffer,
    ) -> Tuple[DetectorResultEnvelope, DetectorResultEnvelope]:
        """
        Runs both Detector A components in parallel on the same validated record.
        Returns (limits_result, statistical_result).
        """
        lim_res = self.evaluate_limits(record)
        stat_res = self.evaluate_statistical(record, history_buffer)
        return lim_res, stat_res


from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel
from ML.models.telemetry import ValidatedTelemetryRecord


class BufferIngestStatus(BaseModel):
    is_duplicate: bool = False
    is_late: bool = False
    message: str = "ok"


class HistoryBuffer:
    """
    Manages in-memory time-ordered recent telemetry history per machine.
    Handles deduplication, out-of-order sequencing, and late-arrival detection.
    """

    def __init__(self, late_threshold_seconds: float = 15.0, max_history_seconds: float = 300.0):
        self.late_threshold_seconds = late_threshold_seconds
        self.max_history_seconds = max_history_seconds
        
        # machine_id -> List of ValidatedTelemetryRecord (kept sorted by measured_at)
        self._machine_history: Dict[str, List[ValidatedTelemetryRecord]] = {}
        
        # Set of seen (machine_id, window_id)
        self._seen_windows: Set[Tuple[str, str]] = set()

    def add(self, record: ValidatedTelemetryRecord) -> BufferIngestStatus:
        identity = (record.machine_id, record.window_id)
        if identity in self._seen_windows:
            return BufferIngestStatus(is_duplicate=True, message=f"Duplicate window {record.window_id} for machine {record.machine_id}")

        self._seen_windows.add(identity)

        if record.machine_id not in self._machine_history:
            self._machine_history[record.machine_id] = []

        history = self._machine_history[record.machine_id]

        # Check late-arrival against the latest known measurement
        is_late = False
        if history:
            latest_time = history[-1].measured_at
            if record.measured_at < latest_time - timedelta(seconds=self.late_threshold_seconds):
                is_late = True

        # Insert record keeping chronological order by measured_at
        history.append(record)
        history.sort(key=lambda r: r.measured_at)

        # Evict records older than max_history_seconds relative to the latest record
        latest_time = history[-1].measured_at
        cutoff_time = latest_time - timedelta(seconds=self.max_history_seconds)
        self._machine_history[record.machine_id] = [r for r in history if r.measured_at >= cutoff_time]

        msg = "Late record ingested for historical reference" if is_late else "Ingested successfully"
        return BufferIngestStatus(is_duplicate=False, is_late=is_late, message=msg)

    def get_recent_history(
        self,
        machine_id: str,
        seconds: float,
        as_of: Optional[datetime] = None,
    ) -> List[ValidatedTelemetryRecord]:
        """
        Returns chronological validated telemetry records within [as_of - seconds, as_of].
        """
        history = self._machine_history.get(machine_id, [])
        if not history:
            return []

        ref_time = as_of or history[-1].measured_at
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        start_time = ref_time - timedelta(seconds=seconds)
        return [r for r in history if start_time <= r.measured_at <= ref_time]

    def clear(self, machine_id: Optional[str] = None):
        """Clear historical buffer for testing or lifecycle reset."""
        if machine_id:
            self._machine_history.pop(machine_id, None)
            self._seen_windows = {ident for ident in self._seen_windows if ident[0] != machine_id}
        else:
            self._machine_history.clear()
            self._seen_windows.clear()


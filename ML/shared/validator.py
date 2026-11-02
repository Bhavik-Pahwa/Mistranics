from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from ML.models.telemetry import (
    RawTelemetryPayload,
    ValidatedTelemetryRecord,
    ValidatedSensorReading,
    ReadingQuality,
)
from ML.shared.units import normalize_unit


class ValidationResult(BaseModel):
    is_valid: bool
    validated_record: Optional[ValidatedTelemetryRecord] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TelemetryValidator:
    """
    Validates decoded telemetry payload, performs unit normalization,
    and constructs a strongly-typed ValidatedTelemetryRecord.
    """

    def validate(self, payload: RawTelemetryPayload) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not payload.machine_id or not payload.machine_id.strip():
            errors.append("machine_id cannot be empty")
        if not payload.device_id or not payload.device_id.strip():
            errors.append("device_id cannot be empty")
        if not payload.reading_id or not payload.reading_id.strip():
            errors.append("reading_id cannot be empty")

        if payload.window_start and payload.window_end:
            if payload.window_start >= payload.window_end:
                errors.append(f"window_start ({payload.window_start}) must precede window_end ({payload.window_end})")
            if not (payload.window_start <= payload.measured_at <= payload.window_end):
                warnings.append(
                    f"measured_at ({payload.measured_at}) lies outside window [{payload.window_start}, {payload.window_end}]"
                )

        if errors:
            return ValidationResult(is_valid=False, validated_record=None, errors=errors, warnings=warnings)

        validated_readings: List[ValidatedSensorReading] = []
        has_suspect_sensor = False

        for r in payload.readings:
            norm_val, norm_unit, conv_ok = normalize_unit(r.parameter, r.value, r.unit)
            quality = r.quality

            if not conv_ok:
                quality = ReadingQuality.suspect
                has_suspect_sensor = True
                warnings.append(f"Sensor {r.sensor_id} ({r.parameter}) has unsupported unit '{r.unit}'")
            elif r.value is None:
                quality = ReadingQuality.missing
                norm_val = None

            validated_readings.append(
                ValidatedSensorReading(
                    sensor_id=r.sensor_id,
                    parameter=r.parameter,
                    value_original=r.value,
                    unit_original=r.unit,
                    value_normalized=norm_val,
                    unit_normalized=norm_unit,
                    quality=quality,
                )
            )

        overall_quality = ReadingQuality.suspect if has_suspect_sensor else ReadingQuality.valid

        record = ValidatedTelemetryRecord(
            schema_version=payload.schema_version,
            machine_id=payload.machine_id.strip(),
            device_id=payload.device_id.strip(),
            window_id=payload.reading_id.strip(),
            measured_at=payload.measured_at,
            window_start=payload.window_start,
            window_end=payload.window_end,
            received_at=payload.received_at,
            ingested_at=datetime.now(timezone.utc),
            operating_context=payload.operating_context,
            readings=validated_readings,
            quality_status=overall_quality,
            quality_warnings=warnings,
        )

        return ValidationResult(is_valid=True, validated_record=record, errors=[], warnings=warnings)


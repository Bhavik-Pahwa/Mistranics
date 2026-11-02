from typing import Tuple, Optional

# Canonical target units for common industrial physical dimensions
CANONICAL_UNITS = {
    "temperature": "degC",
    "pressure": "kPa",
    "vibration": "mm/s",
    "current": "A",
    "power": "kW",
    "speed": "rpm",
}

# Parameter to physical dimension mapping
PARAMETER_DIMENSION_MAP = {
    # Temperature
    "temperature": "temperature",
    "motor_temperature": "temperature",
    "bearing_temperature": "temperature",
    "winding_temperature": "temperature",
    "mean_temperature": "temperature",
    "min_temperature": "temperature",
    "max_temperature": "temperature",
    
    # Pressure
    "pressure": "pressure",
    "mean_pressure": "pressure",
    "suction_pressure": "pressure",
    "discharge_pressure": "pressure",
    "oil_pressure": "pressure",
    
    # Vibration
    "vibration": "vibration",
    "vibration_rms": "vibration",
    "peak_rms": "vibration",
    "peak_vibration": "vibration",
    
    # Current
    "current": "current",
    "mean_current": "current",
    "motor_current": "current",
    "phase_current": "current",
    
    # Power / Output
    "output": "power",
    "mean_output": "power",
    "power": "power",
    "output_power": "power",
    
    # Speed
    "rpm": "speed",
    "rotational_speed": "speed",
}


def normalize_unit(parameter: str, value: Optional[float], unit: str) -> Tuple[Optional[float], str, bool]:
    """
    Normalizes a sensor measurement to its canonical unit.
    Returns: (normalized_value, canonical_unit, is_valid_conversion)
    - If value is None, returns (None, canonical_unit, True).
    - If unit conversion is successful, returns (val, canonical_unit, True).
    - If unit is unknown or incompatible, returns (value, unit, False).
    """
    dim = PARAMETER_DIMENSION_MAP.get(parameter.lower())
    clean_unit = unit.strip().lower()

    if value is None:
        target_unit = CANONICAL_UNITS.get(dim, unit)
        return None, target_unit, True

    if dim == "temperature":
        target_unit = "degC"
        if clean_unit in ["degc", "c", "celsius"]:
            return float(value), target_unit, True
        elif clean_unit in ["degf", "f", "fahrenheit"]:
            return (float(value) - 32.0) * 5.0 / 9.0, target_unit, True
        elif clean_unit in ["k", "kelvin"]:
            return float(value) - 273.15, target_unit, True
        else:
            return value, unit, False

    elif dim == "pressure":
        target_unit = "kPa"
        if clean_unit in ["kpa"]:
            return float(value), target_unit, True
        elif clean_unit in ["bar"]:
            return float(value) * 100.0, target_unit, True
        elif clean_unit in ["mbar"]:
            return float(value) * 0.1, target_unit, True
        elif clean_unit in ["psi"]:
            return float(value) * 6.894757293, target_unit, True
        elif clean_unit in ["pa"]:
            return float(value) / 1000.0, target_unit, True
        elif clean_unit in ["mpa"]:
            return float(value) * 1000.0, target_unit, True
        else:
            return value, unit, False

    elif dim == "vibration":
        target_unit = "mm/s"
        if clean_unit in ["mm/s", "mms"]:
            return float(value), target_unit, True
        elif clean_unit in ["in/s", "ips"]:
            return float(value) * 25.4, target_unit, True
        elif clean_unit in ["m/s", "ms"]:
            return float(value) * 1000.0, target_unit, True
        else:
            return value, unit, False

    elif dim == "current":
        target_unit = "A"
        if clean_unit in ["a", "amp", "amps"]:
            return float(value), target_unit, True
        elif clean_unit in ["ma"]:
            return float(value) / 1000.0, target_unit, True
        elif clean_unit in ["ka"]:
            return float(value) * 1000.0, target_unit, True
        else:
            return value, unit, False

    elif dim == "power":
        target_unit = "kW"
        if clean_unit in ["kw"]:
            return float(value), target_unit, True
        elif clean_unit in ["w"]:
            return float(value) / 1000.0, target_unit, True
        elif clean_unit in ["mw"]:
            return float(value) * 1000.0, target_unit, True
        elif clean_unit in ["hp"]:
            return float(value) * 0.745699872, target_unit, True
        else:
            return value, unit, False

    elif dim == "speed":
        target_unit = "rpm"
        if clean_unit in ["rpm"]:
            return float(value), target_unit, True
        elif clean_unit in ["hz"]:
            return float(value) * 60.0, target_unit, True
        elif clean_unit in ["rad/s", "rads"]:
            return float(value) * (30.0 / 3.141592653589793), target_unit, True
        else:
            return value, unit, False

    # Default fallback when parameter is not in mapping
    return float(value), unit, True


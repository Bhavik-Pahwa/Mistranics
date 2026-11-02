"""Temperature conditions extracted unchanged from the existing CLI simulator.

This is a deterministic evaluation model, not a physical motor thermal model.
"""


def motor_temperature(step: int, steps: int, with_anomaly: bool) -> float:
    return 82.0 if with_anomaly and step >= steps - 3 else 52.0

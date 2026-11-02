import math
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from app.simulator import MotorModel


def test_thermal_model_and_pause():
    model = MotorModel(seed=1)
    for _ in range(500):
        model.step()
    assert model.temperature == pytest.approx(37 + (28 - 37) * (1 - 0.02 / 12) ** 500)
    previous = model.temperature
    model.paused = True
    model.step()
    assert model.temperature == previous
    model.paused = False
    model.mode = "heat"
    model.severity = 100
    model.step()
    assert model.temperature > previous


@pytest.mark.parametrize("mode", ["normal", "imb", "mis", "brg", "loose", "heat"])
def test_all_modes_generate_bounded_finite_sensors(mode):
    model = MotorModel(seed=123)
    model.mode = mode
    for _ in range(200):
        model.step()
    assert all(len(values) == 400 for values in model.buffers.values())
    assert all(math.isfinite(v) for values in model.buffers.values() for v in values)
    assert 0 <= model.rms < 10
    assert len(model.history) <= 120 and len(model.lines) <= 40


def test_serial_window_uses_only_real_received_samples(monkeypatch):
    # Optional USB transport dependency is isolated from the regular server requirements.
    pytest.importorskip("serial")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from backend.examples.serial_sensor import SerialWindows, parse_temperature
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    windows = SerialWindows("device-01")
    assert parse_temperature("boot message") is None
    assert parse_temperature("Temperature: 29.62°C  ~  85.32°F") == 29.62
    windows.advance(now)
    windows.add(29.62)
    result = windows.advance(now + timedelta(seconds=3))
    assert result["source"] == "physical"
    assert result["temperature"]["sample_count"] == 1
    assert result["temperature"]["mean"] == 29.62
    assert windows.advance(now + timedelta(seconds=6)) is None
    windows.add(-127)
    result = windows.advance(now + timedelta(seconds=9))
    assert result["temperature"]["status"] == "disconnected"
    assert result["temperature"]["mean"] is None

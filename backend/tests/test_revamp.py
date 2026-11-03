"""Multi-sensor transport, validation, and workspace isolation regression tests."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.config import Settings
from app.main import create_app
from app.simulator import MotorModel, MotorSimulator, SimulationControl
from app.telemetry import TelemetryState, Window
from test_iot import payload, settings

@pytest.mark.parametrize('mode', ['normal', 'imb', 'mis', 'brg', 'loose', 'heat', 'over', 'short', 'stall'])
def test_current_port_and_modes(mode):
    model = MotorModel(seed=7)
    model.mode, model.severity = mode, 100
    for _ in range(100):
        model.step()
    expected = 1.6 + {'normal': 0, 'imb': .05, 'mis': .15, 'brg': .25, 'loose': .03, 'heat': .1, 'over': 1.6, 'short': 1.5, 'stall': 4.5}[mode]
    assert model.current == pytest.approx(expected, abs=.08)
    assert len(model.buffers['cur']) == 400
    if mode in ('over', 'short', 'stall'):
        assert model.demo_status() == 'FAULT'
    model.rpm = 0
    for _ in range(100):
        model.step()
    assert model.current < .0001


def test_mqtt_publishes_every_sensor_and_temperature():
    motor = MotorSimulator(settings())
    messages = []
    motor.connected = True
    motor.client.publish = lambda topic, body, **options: messages.append((topic, json.loads(body), options)) or SimpleNamespace(rc=0, mid=1)
    for tick in range(4):
        for _ in range(50):
            motor.model.step()
        motor.collect(float(tick))
    assert len(messages) == 1
    topic, body, options = messages[0]
    record = Window.model_validate(body)
    assert options == {'qos': 1, 'retain': False}
    assert record.temperature.sample_count == 3
    assert set(record.sensors) == {'current', 'vibration', 'rpm', 'ax', 'ay', 'az', 'gx', 'gy', 'gz'}
    assert record.sensors['current'].unit == 'A'
    assert record.sensors['vibration'].unit == 'g'
    assert record.sensors['gx'].unit == 'deg/s'
    assert all(r.sample_count == 3 for r in record.sensors.values())
    assert record.sensors['current'].mean > 1
    motor.control(SimulationControl(paused=True))
    motor.collect(7)
    assert len(messages) == 1


def sensor(value=1.6, unit='A'):
    return dict(mean=value, min=value, max=value, unit=unit, status='valid', sample_count=3)


@pytest.mark.parametrize('change', [dict(unit='g'), dict(mean=float('nan')), dict(min=10.), dict(mean='1.6'), dict(sample_count=0), dict(mean=-1., min=-1., max=-1.), dict(status='error')])
def test_bad_sensor_windows_rejected(change):
    data = payload()
    data['sensors'] = {'current': sensor() | change}
    with pytest.raises(ValidationError):
        Window.model_validate(data)


def test_sensor_detectors_independent_and_duplicates_do_not_train():
    cfg = settings(telemetry_stale_after_seconds=30)
    state = TelemetryState(cfg)
    state.selected_at -= timedelta(seconds=30)
    state.connected(True)
    end = datetime.now(timezone.utc) - timedelta(seconds=18)
    for i in range(7):
        record = payload(sequence=i+1, value=32., end=end + timedelta(seconds=3*i))
        record['sensors'] = {'current': sensor(4. if i == 6 else 1.6), 'vibration': sensor(.02, 'g')}
        state.consume(record)
        state.consume(record)
    readings = state.latest['readings']
    assert readings['temperature']['anomaly']['status'] == 'NORMAL'
    assert readings['vibration']['anomaly']['status'] == 'NORMAL'
    assert readings['current']['anomaly']['status'] == 'ANOMALY'
    assert readings['current']['anomaly']['baseline_samples'] == 6
    assert len(state.history) == 7


def test_workspace_streams_are_independent_and_legacy_switch_is_isolated():
    app = create_app(settings())
    with TestClient(app) as client:
        for source in ('simulation', 'physical'):
            app.state.streams[source].consume(payload(source=source))
        assert client.get('/api/status?source=physical').json()['latest']['device_id'] == 'device-01'
        assert client.get('/api/status?source=simulation').json()['latest']['device_id'] == 'simulation-01'
        client.post('/api/source', json={'source': 'simulation'})
        with client.websocket_connect('/ws/telemetry?source=physical') as ws:
            assert ws.receive_json()['source'] == 'physical'
        assert len(client.get('/api/status?source=physical').json()['history']) == 1
        assert client.get('/api/status?source=invalid').status_code == 422
        for mode in ('over', 'short', 'stall'):
            assert client.patch('/api/simulation', json={'mode': mode}).json()['mode'] == mode
        assert 'ACS712' in client.get('/simulator').text


def test_publisher_can_be_disabled_on_startup():
    simulator = MotorSimulator(settings(simulator_publish_enabled=False))
    simulator.collect(0)
    assert simulator.window is None

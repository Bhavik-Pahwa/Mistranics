"""Optional real-browser checks against a running IoT backend, Vite, and MQTT broker.

Synthetic physical-source packets below test software only; they are NOT probe evidence.
Set RUN_BROWSER_TESTS=1, IOT_TEST_URL and MQTT_HOST/MQTT_PORT. Install playwright separately.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest

from app.config import Settings
from app.mqtt import configure_client
from test_iot import payload


@pytest.mark.skipif(not os.getenv("RUN_BROWSER_TESTS"), reason="Optional running-stack browser test")
def test_live_dashboard_and_browser_simulator():
    from playwright.sync_api import sync_playwright, expect

    cfg = Settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    configure_client(client, cfg)
    client.connect(cfg.mqtt_host, cfg.mqtt_port)
    client.loop_start()
    sequence = time.time_ns() // 1000
    artifacts = Path(__file__).resolve().parents[2] / ".iot-test"
    artifacts.mkdir(exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv("PLAYWRIGHT_CHANNEL", "chrome"))
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            url = os.getenv("IOT_TEST_URL", "http://127.0.0.1:5173")
            page.request.patch(url + "/api/simulation", data={"publisher_enabled": False, "paused": False})
            page.goto(url)
            panel = page.get_by_role("region", name="Live temperature telemetry")
            select = panel.get_by_label("Telemetry data source")
            expect(select).to_be_enabled()
            select.select_option("simulation")
            expect(select).to_have_value("simulation")
            select.select_option("physical")
            expect(select).to_have_value("physical")
            for index, value in enumerate([32, 32.1, 31.9, 32.1, 31.9, 32, 48]):
                if index:
                    # Real three-second acquisition cadence, not a UI synchronization sleep.
                    threading.Event().wait(3.05)
                record = payload(sequence + index, value=value)
                client.publish(cfg.iot_topic, json.dumps(record), qos=1).wait_for_publish(3)
                expect(panel.get_by_test_id("temperature-value")).to_have_text(f"{value:.2f} °C")
                status = "WARMING UP" if index < 5 else "NORMAL" if index == 5 else "ANOMALY"
                expect(panel.get_by_role("status")).to_have_text(status)
            expect(panel.get_by_role("img").locator('circle[fill="#e11d48"]')).to_have_count(1)
            page.screenshot(path=str(artifacts / "statistical-anomaly.png"), full_page=True)
            expect(panel.get_by_role("status")).to_have_text("DISCONNECTED", timeout=14000)
            record = payload(sequence + 7)
            record["temperature"].update(mean=None, min=None, max=None, sample_count=0, status="disconnected")
            client.publish(cfg.iot_topic, json.dumps(record), qos=1).wait_for_publish(3)
            expect(panel.get_by_role("status")).to_have_text("SENSOR ERROR")
            expect(panel.get_by_test_id("temperature-value")).to_have_text("— °C")
            # Failed selection must keep the last confirmed source.
            page.route("**/api/source", lambda route: route.fulfill(status=503, body="unavailable"))
            select.select_option("simulation")
            expect(panel.get_by_role("alert")).to_contain_text("Source selection failed")
            expect(select).to_have_value("physical")
            page.unroute("**/api/source")
            select.select_option("simulation")
            expect(select).to_have_value("simulation")
            expect(panel.get_by_role("img").locator("circle")).to_have_count(0)
            simulator = context.new_page()
            simulator.on("pageerror", lambda error: errors.append(str(error)))
            simulator.goto(url + "/simulator")
            simulator.get_by_role("button", name="Start INDUX publisher").click()
            expect(simulator.locator("#publish-status")).to_contain_text(re.compile(r"[1-9]\d* acknowledged windows"), timeout=12000)
            expect(panel.get_by_test_id("temperature-value")).not_to_have_text("— °C")
            expect(panel.get_by_role("status")).to_have_text("WARMING UP")
            simulator.get_by_role("button", name="Overheating", exact=True).click()
            simulator.locator("#rpm").fill("2000")
            expect(simulator.locator("#rv")).to_have_text("2000 RPM")
            simulator.locator("#sev").fill("90")
            expect(simulator.locator("#sv")).to_have_text("90%")
            expect(simulator.locator("#rv")).to_have_text("2000 RPM")
            simulator.get_by_role("button", name="Pause", exact=True).click()
            expect(panel.get_by_role("status")).to_have_text("DISCONNECTED", timeout=14000)
            simulator.get_by_role("button", name="Resume", exact=True).click()
            expect(panel.get_by_text("Stream: Live", exact=True)).to_be_visible(timeout=12000)
            # Closing all simulator viewers must not stop publication or reset controls.
            previous = page.request.get(url + "/api/status").json()["latest"]["sequence"]
            simulator.close()
            page.wait_for_function("async (previous) => (await (await fetch('/api/status')).json()).latest.sequence > previous", arg=previous, timeout=10000)
            simulator = context.new_page()
            simulator.on("pageerror", lambda error: errors.append(str(error)))
            simulator.goto(url + "/simulator")
            expect(simulator.locator("#rv")).to_have_text("2000 RPM")
            expect(simulator.locator("#sv")).to_have_text("90%")
            expect(simulator.get_by_role("button", name="Stop INDUX publisher")).to_be_enabled()
            context.set_offline(True)
            expect(panel.get_by_text("WebSocket: Disconnected · retrying")).to_be_visible(timeout=10000)
            context.set_offline(False)
            expect(panel.get_by_text("WebSocket: Connected")).to_be_visible(timeout=20000)
            expect(panel.get_by_text("Stream: Live", exact=True)).to_be_visible(timeout=20000)
            page.screenshot(path=str(artifacts / "browser-simulation.png"), full_page=True)
            simulator.screenshot(path=str(artifacts / "server-simulator.png"), full_page=True)
            simulator.get_by_role("button", name="Stop INDUX publisher").click()
            page.set_viewport_size({"width": 390, "height": 844})
            expect(select).to_be_visible()
            expect(panel.get_by_role("img")).to_be_in_viewport()
            page.screenshot(path=str(artifacts / "mobile.png"), full_page=True)
            assert not errors, errors
            browser.close()
    finally:
        client.disconnect()
        client.loop_stop()

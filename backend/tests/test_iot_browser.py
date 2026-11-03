"""Optional browser coverage for the two workspaces against a running local stack.

Set RUN_BROWSER_TESTS=1, IOT_TEST_URL, MQTT_HOST, MQTT_PORT.
Physical packets in this test are synthetic test fixtures, not hardware evidence.
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

pytestmark = pytest.mark.skipif(not os.getenv('RUN_BROWSER_TESTS'), reason='Optional running-stack browser test')
ARTIFACTS = Path(__file__).resolve().parents[2] / '.iot-test'


def test_industrial_navigation_admin_chat_and_mobile():
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv('PLAYWRIGHT_CHANNEL', 'chrome'))
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        url = os.getenv('IOT_TEST_URL', 'http://127.0.0.1:5173')
        page.goto(url)
        expect(page.get_by_role('heading', name=re.compile('Know what'))).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / 'revamp-entry.png'), full_page=True)
        page.get_by_role('button', name=re.compile('Industrial Mode')).click()
        expect(page.get_by_label('Machine telemetry')).to_have_value('simulation-01')
        expect(page.get_by_role('button', name='Motor current', exact=True)).to_be_visible(timeout=10000)
        page.get_by_role('button', name='Motor current', exact=True).click()
        expect(page.get_by_role('heading', name='Motor current', exact=True)).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / 'revamp-industrial.png'), full_page=True)
        page.get_by_role('button', name='Investigations', exact=True).click()
        expect(page.get_by_role('heading', name='Investigations', exact=True)).to_be_visible()
        page.get_by_role('button', name=re.compile('Open investigation')).first.click()
        expect(page.get_by_role('dialog')).to_be_visible()
        expect(page.get_by_role('heading', name='Recommended troubleshooting')).to_be_visible()
        page.get_by_role('button', name='Mark resolved').click()
        expect(page.get_by_role('dialog').get_by_text(re.compile('Resolved '))).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / 'revamp-investigation.png'), full_page=True)
        page.keyboard.press('Escape')
        expect(page.get_by_role('dialog')).to_have_count(0)
        page.get_by_role('button', name='Knowledge Manuals').click()
        page.get_by_role('button', name=re.compile('MTR-001 · PROTOTYPE GUIDE')).click()
        expect(page.get_by_role('heading', name='Sensor inspection')).to_be_visible()
        page.keyboard.press('Escape')
        page.get_by_role('button', name='Admin', exact=True).click()
        expect(page.get_by_role('heading', name='Admin access')).to_be_visible()
        page.get_by_label('Email address').fill('admin@mistranics.com')
        page.get_by_label('Password', exact=True).fill('bad-password')
        page.get_by_role('button', name='Sign in').click()
        expect(page.get_by_role('alert')).to_contain_text('credentials')
        page.get_by_label('Password', exact=True).fill('admin123')
        page.get_by_role('button', name='Sign in').click()
        page.get_by_role('button', name='Onboard machine').click()
        dialog = page.get_by_role('dialog')
        for label, value in [('name', 'QA motor'), ('Machine code', 'QA-001'), ('type', 'Induction motor'), ('location', 'QA bench')]:
            dialog.get_by_label(label, exact=True).fill(value)
        dialog.get_by_role('checkbox', name='rpm', exact=True).check()
        dialog.get_by_role('button', name='Save machine').click()
        expect(page.get_by_role('heading', name='QA motor', exact=True)).to_be_visible()
        row = page.get_by_role('article').filter(has=page.get_by_role('heading', name='QA motor', exact=True))
        row.get_by_role('button', name='Edit machine').click()
        dialog.get_by_label('name', exact=True).fill('QA motor updated')
        dialog.get_by_role('checkbox', name='current', exact=True).uncheck()
        dialog.get_by_role('button', name='Save machine').click()
        expect(page.get_by_role('heading', name='QA motor updated')).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / 'revamp-admin.png'), full_page=True)
        page.get_by_role('button', name='Chatbot', exact=True).click()
        page.get_by_label('Target machine').select_option(label='QA motor updated')
        page.get_by_role('textbox', name='Message about the selected machine').fill('Check my motor')
        page.get_by_role('button', name='Send message').click()
        expect(page.get_by_text('Check my motor', exact=True).last).to_be_visible()
        page.get_by_label('Target machine').select_option('simulation-01')
        expect(page.get_by_role('button', name='Check my motor', exact=True)).to_have_count(0)
        page.get_by_label('Target machine').select_option(label='QA motor updated')
        page.get_by_role('button', name='Check my motor', exact=True).click()
        expect(page.get_by_text(re.compile('There are no telemetry readings'))).to_be_visible()
        page.get_by_role('button', name='New conversation').click()
        page.screenshot(path=str(ARTIFACTS / 'revamp-chat.png'), full_page=True)
        page.reload()
        page.get_by_role('button', name=re.compile('Industrial Mode')).click()
        page.get_by_label('Machine telemetry').select_option(label='QA motor updated')
        page.get_by_role('button', name='Chatbot', exact=True).click()
        page.get_by_label('Target machine').select_option(label='QA motor updated')
        expect(page.get_by_role('button', name='Check my motor', exact=True)).to_be_visible()
        page.get_by_role('button', name='Return to workspace selection').click()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(ARTIFACTS / 'revamp-mobile-entry.png'), full_page=True)
        page.get_by_role('button', name=re.compile('Industrial Mode')).click()
        page.screenshot(path=str(ARTIFACTS / 'revamp-mobile-industrial.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        browser.close()


def test_physical_anomaly_and_workspace_isolation():
    from playwright.sync_api import sync_playwright, expect
    cfg = Settings()
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    configure_client(publisher, cfg)
    publisher.connect(cfg.mqtt_host, cfg.mqtt_port)
    publisher.loop_start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv('PLAYWRIGHT_CHANNEL', 'chrome'))
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            url = os.getenv('IOT_TEST_URL', 'http://127.0.0.1:5173')
            page.goto(url)
            page.get_by_role('button', name=re.compile('Hands-on Mode')).click()
            expect(page.get_by_role('heading', name='Temperature', exact=True)).to_be_visible()
            industrial = context.new_page()
            industrial.goto(url)
            industrial.get_by_role('button', name=re.compile('Industrial Mode')).click()
            sequence = time.time_ns() // 1000
            for index, value in enumerate([32, 32.1, 31.9, 32.1, 31.9, 32, 48]):
                if index:
                    threading.Event().wait(3.05)  # Sensor acquisition cadence, not a UI wait.
                publisher.publish(cfg.iot_topic, json.dumps(payload(sequence+index, value=value)), qos=1).wait_for_publish(3)
            expect(page.get_by_role('heading', name='Temperature anomaly detected').first).to_be_visible(timeout=10000)
            expect(page.get_by_text('48.00 degC', exact=True).first).to_be_visible()
            expect(page.get_by_role('img', name=re.compile('Temperature readings')).locator('circle[fill="#e34d59"]')).not_to_have_count(0)
            expect(industrial.get_by_role('button', name='Motor current', exact=True)).to_be_visible()
            assert page.request.get(url + '/api/status?source=simulation').json()['latest']['source'] == 'simulation'
            assert page.request.get(url + '/api/status?source=physical').json()['latest']['source'] == 'physical'
            page.screenshot(path=str(ARTIFACTS / 'revamp-physical-anomaly.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(ARTIFACTS / 'revamp-mobile-physical.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            simulator = context.new_page()
            simulator.goto(url + '/simulator')
            expect(simulator.get_by_role('button', name='Winding short', exact=True)).to_be_enabled()
            industrial.get_by_role('button', name='Motor current', exact=True).click()
            simulator.get_by_role('button', name='Winding short', exact=True).click()
            expect(simulator.get_by_role('button', name='Winding short', exact=True)).to_have_attribute('aria-pressed', 'true')
            expect(simulator.locator('#cur')).to_contain_text('A')
            expect(industrial.get_by_label('Sensor detection')).to_contain_text('ANOMALY', timeout=12000)
            industrial.get_by_role('button', name='Investigations', exact=True).click()
            expect(industrial.get_by_role('heading', name='Motor current deviation').first).to_be_visible()
            simulator.get_by_role('button', name='Normal', exact=True).click()
            simulator.screenshot(path=str(ARTIFACTS / 'revamp-simulator.png'), full_page=True)
            assert not errors, errors
            browser.close()
    finally:
        publisher.disconnect()
        publisher.loop_stop()

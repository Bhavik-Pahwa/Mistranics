"""Opt-in browser acceptance using the live backend and real local Ollama."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors, responses = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def response_received(response):
            if response.url.endswith("/api/industrial/chat"):
                responses.append({"status": response.status, "body": response.json()})
        page.on("response", response_received)
        page.goto("http://127.0.0.1:5173")
        page.get_by_role("button", name="01 / SIMULATED OPERATIONS", exact=False).click()
        page.get_by_role("button", name="Knowledge Manuals", exact=True).click()
        expect(page.locator(".simulation-manuals .manual-card")).to_have_count(3, timeout=10000)
        page.get_by_role("button", name="Chatbot", exact=True).click()
        page.get_by_label("Target machine").select_option("simulation-01")
        page.get_by_role("textbox", name="Message about the selected machine").fill(
            "What virtual checks distinguish winding short and electrical ripple with a fixed-frequency hum?"
        )
        page.get_by_role("button", name="Send message").click()
        expect(page.locator(".grounded-answer")).to_be_visible(timeout=380000)
        expect(page.locator(".grounded-answer .answer-sources a").first).to_have_attribute("href", "/api/industrial/manuals/SIM-MTR-FAULTS/pdf#page=9")
        assert responses and responses[-1]["status"] == 200, responses
        assert responses[-1]["body"]["model"] == "llama3.2:1b"
        assert not errors, errors
        page.screenshot(path=str(ROOT / ".iot-test/simulation-rag-ui.png"), full_page=True)
        report = {"browser_passed": True, "page_errors": errors, "response": responses[-1]}
        (ROOT / ".iot-test/simulation-rag-ui.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"browser_passed": True, "http_status": responses[-1]["status"], "sources": responses[-1]["body"]["sources"], "page_errors": errors}), flush=True)
        browser.close()


if __name__ == "__main__":
    main()

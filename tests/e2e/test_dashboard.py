from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from acnopviz.api import create_app
from acnopviz.config import Settings

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def live_url(tmp_path_factory):
    port = _free_port()
    settings = Settings(db_path=tmp_path_factory.mktemp("e2e") / "e2e.db", bootstrap_paths=300)
    app = create_app(settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


def test_dashboard_review_scenario_and_exports(browser, live_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_url)
    expect(page.locator("#view-title")).to_have_text("Overview")
    expect(page.locator(".kpi-value").first).not_to_be_empty()
    page.locator('.nav-item[data-view="recommendations"]').click()
    expect(page.locator("#view-title")).to_have_text("Recommendations")
    card = page.locator(".rec").first
    card.locator(".review-status").select_option("accepted")
    card.locator(".review-note").fill("E2E review note")
    card.locator(".save-review").click()
    expect(page.locator("#toast")).to_contain_text("Review saved")
    page.get_by_role("button", name="Review audit").click()
    expect(page.locator(".audit-item").first).to_contain_text("E2E review note")
    page.get_by_role("button", name="Scenario lab").click()
    expect(page.locator("#scenario-result")).to_contain_text("Baseline P(negative)")
    page.locator("#expense_reduction").evaluate(
        "el => { el.value = '0.1'; el.dispatchEvent(new Event('input', { bubbles: true })); }"
    )
    page.get_by_role("button", name="Run scenario").click()
    expect(page.locator("#scenario-result")).to_contain_text("Scenario median ending cash")
    page.get_by_role("button", name="Transactions").click()
    expect(page.locator("table tbody tr").first).to_be_visible()
    page.locator("#tx-type").select_option("ar")
    page.get_by_role("button", name="Apply").click()
    expect(page.locator("table tbody tr").first).to_contain_text("AR")
    page.get_by_role("button", name="Data quality").click()
    expect(page.locator("#view-quality")).to_contain_text("Duplicate-payment candidates")
    page.get_by_role("button", name="Methodology").click()
    expect(page.locator("#view-method")).to_contain_text("Wilson interval")
    assert not errors, errors
    page.close()


def test_mobile_navigation(browser, live_url):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(live_url)
    expect(page.locator("#view-title")).to_have_text("Overview")
    page.get_by_role("button", name="Scenario lab").click()
    expect(page.locator("#scenario-form")).to_be_visible()
    page.close()


def test_v11_calendar_backtest_and_import(browser, live_url, tmp_path):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_url)
    page.locator('.nav-item[data-view="calendar"]').click()
    expect(page.locator("#view-title")).to_have_text("Cash calendar")
    expect(page.locator("#cal-result")).to_contain_text("P(negative month-end)")
    expect(page.locator("#cal-result table tbody tr")).to_have_count(6)
    page.locator('.nav-item[data-view="backtest"]').click()
    expect(page.locator("#bt-result")).to_contain_text("Bootstrap MAE")
    page.locator('.nav-item[data-view="import"]').click()
    fixture = (
        Path(__file__).resolve().parents[2] / "data" / "synthetic" / "improvements" / "valid_bundle"
    )
    page.locator("#imp-manifest").set_input_files(str(fixture / "manifest.json"))
    for table in ["customers", "vendors", "invoices", "bills", "cash_transactions"]:
        page.locator(f"#imp-{table}").set_input_files(str(fixture / f"{table}.csv"))
    page.get_by_role("button", name="Validate bundle").click()
    expect(page.locator("#imp-result")).to_contain_text("Valid bundle")
    page.locator("#imp-confirm").check()
    page.get_by_role("button", name="Commit replace").click()
    expect(page.locator("#toast")).to_contain_text("Ledger replaced")
    page.locator('.nav-item[data-view="audit"]').click()
    expect(page.locator("#view-audit")).to_contain_text("dataset.import")
    expect(page.locator("#view-audit")).not_to_contain_text("undefined")
    page.locator('.nav-item[data-view="quality"]').click()
    expect(page.locator("#view-quality")).to_contain_text('"seed": 111')
    assert not errors, errors
    page.close()


def test_import_file_change_invalidates_validation(browser, live_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(live_url)
    page.locator('.nav-item[data-view="import"]').click()
    root = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "improvements"
    valid = root / "valid_bundle"
    page.locator("#imp-manifest").set_input_files(str(valid / "manifest.json"))
    for table in ["customers", "vendors", "invoices", "bills", "cash_transactions"]:
        page.locator(f"#imp-{table}").set_input_files(str(valid / f"{table}.csv"))
    page.get_by_role("button", name="Validate bundle").click()
    expect(page.locator("#imp-result")).to_contain_text("Valid bundle")
    expect(page.locator("#imp-commit")).to_be_enabled()
    page.locator("#imp-bills").set_input_files(str(root / "invalid_bundle" / "bills.csv"))
    expect(page.locator("#imp-commit")).to_be_disabled()
    expect(page.locator("#imp-result")).to_contain_text("Validate again")
    page.close()


def test_async_action_errors_are_shown(browser, live_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_url)
    page.locator('.nav-item[data-view="scenario"]').click()
    expect(page.locator("#scenario-result")).to_contain_text("Baseline P(negative)")
    page.route("**/api/scenario", lambda route: route.abort())
    page.get_by_role("button", name="Run scenario").click()
    expect(page.locator("#alert")).to_be_visible()
    assert not errors, errors
    page.close()


def test_calendar_chart_last_label_is_not_clipped(browser, live_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(live_url)
    page.locator('.nav-item[data-view="calendar"]').click()
    page.wait_for_selector("#cal-result svg")
    last = page.locator("#cal-result svg text").last
    expect(last).to_have_attribute("text-anchor", "end")
    page.close()

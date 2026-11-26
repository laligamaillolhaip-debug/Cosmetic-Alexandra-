import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "http://127.0.0.1:8011"
SERVER_SCRIPT = Path(__file__).with_name("server.py")


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("yadro-e2e")
    env = os.environ.copy()
    env["E2E_DB_PATH"] = str(temp_dir / "e2e.sqlite")
    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 40
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"E2E server exited before startup.\n{stdout}\n{stderr}")
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/meta/options", timeout=1) as response:
                ready = response.status == 200
            if ready:
                break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    if not ready:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        pytest.fail(f"E2E server did not become ready.\n{stdout}\n{stderr}")

    yield BASE_URL

    process.terminate()
    process.wait(timeout=10)
    process.stdout.close()
    process.stderr.close()


@pytest.fixture(scope="session")
def browser(e2e_server):
    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch(headless=True)
        yield browser_instance
        browser_instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page_instance = context.new_page()
    yield page_instance
    context.close()


@pytest.mark.e2e
def test_signup_quiz_ai_plan_and_chat_persist(page):
    email = f"e2e-{time.time_ns()}@example.test"
    page.goto(f"{BASE_URL}/login.html")
    page.get_by_role("button", name="Регистрация").click()
    page.locator("#email").fill(email)
    page.locator("#password").fill("secret123")
    page.locator("#submitBtn").click()

    expect(page).to_have_url(f"{BASE_URL}/quiz.html")
    next_button = page.locator("#nextBtn")
    expect(next_button).to_be_disabled()
    page.locator('#skinTypeOptions .option-card[data-id="normal"]').click()
    expect(next_button).to_be_enabled()
    next_button.click()
    expect(page.locator("#stepLabel")).to_have_text("Шаг 2 из 2")
    next_button.click()

    expect(page).to_have_url(f"{BASE_URL}/budget.html")
    page.locator("#budgetSlider").evaluate(
        "(slider) => { slider.value = '20000'; slider.dispatchEvent(new Event('input', { bubbles: true })); }"
    )
    page.locator("#submitBtn").click()
    expect(page).to_have_url(f"{BASE_URL}/plan.html")
    expect(page.locator("#planOrigin")).to_have_text("Базовый подбор")

    page.locator("#generatePlan").click()
    expect(page.locator("#aiDraft")).to_be_visible(timeout=15000)
    expect(page.locator("#draftSummary")).to_have_text("Deterministic test proposal")
    page.locator("#applyDraft").click()
    expect(page.locator("#planOrigin")).to_have_text("Подобрано с ИИ")

    page.goto(f"{BASE_URL}/chat.html")
    expect(page.locator("#chatStatus")).to_have_text("История сохраняется")
    page.locator("#chatInput").fill("Как наносить средства?")
    page.locator("#sendBtn").click()
    expect(page.locator("#chatArea")).to_contain_text("Deterministic E2E answer")

    page.reload()
    expect(page.locator("#chatArea")).to_contain_text("Как наносить средства?")
    expect(page.locator("#chatArea")).to_contain_text("Deterministic E2E answer")


@pytest.mark.e2e
def test_browser_context_does_not_inherit_another_users_profile(browser, e2e_server):
    context = browser.new_context()
    page_instance = context.new_page()

    page_instance.goto(f"{BASE_URL}/plan.html")

    expect(page_instance).to_have_url(f"{BASE_URL}/login.html")
    assert page_instance.evaluate("localStorage.getItem('yadro_profile_id')") is None
    context.close()


@pytest.mark.e2e
def test_browser_native_validation_blocks_invalid_registration(page):
    page.goto(f"{BASE_URL}/login.html")
    page.get_by_role("button", name="Регистрация").click()
    page.locator("#email").fill("not-an-email")
    page.locator("#password").fill("12345")

    assert page.locator("#email").evaluate("(input) => input.checkValidity()") is False
    assert page.locator("#password").evaluate("(input) => input.checkValidity()") is False
    page.locator("#submitBtn").click()
    expect(page).to_have_url(f"{BASE_URL}/login.html")

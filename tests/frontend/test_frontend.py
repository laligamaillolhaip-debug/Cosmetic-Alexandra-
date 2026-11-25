from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


@pytest.mark.parametrize("page", [
    "login.html",
    "index.html",
    "quiz.html",
    "budget.html",
    "plan.html",
    "catalog.html",
    "product.html",
    "calendar.html",
    "chat.html",
    "profile.html",
])
def test_frontend_pages_exist(page):
    assert (FRONTEND / page).is_file()


def test_login_page_registers_with_auth_api():
    html = (FRONTEND / "login.html").read_text(encoding="utf-8")

    assert 'id="email"' in html
    assert 'id="password"' in html
    assert 'data-mode="register"' in html
    assert "/api/auth/${mode}" in html
    assert 'window.location.href = "quiz.html"' in html


def test_api_script_exposes_auth_and_credentials_storage():
    api_js = (FRONTEND / "js" / "api.js").read_text(encoding="utf-8")

    assert 'const API_BASE = "";' in api_js
    assert "credentials: \"same-origin\"" in api_js
    assert 'async me()' in api_js
    assert 'async logout()' in api_js
    assert "setEmail(v)" in api_js


def test_javascript_frontend_unit_suite():
    node = shutil.which("node")
    assert node, "Node.js is required for the frontend unit tests"

    result = subprocess.run(
        [node, "--test", "tests/frontend/frontend.test.js"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr

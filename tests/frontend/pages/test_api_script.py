# Контракт API
from pathlib import Path


def test_api_script_exposes_auth_and_credentials_storage():
    root = Path(__file__).resolve().parents[3]
    api_js = (root / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    assert 'const API_BASE = "";' in api_js
    assert 'credentials: "same-origin"' in api_js
    assert "async me()" in api_js
    assert "async logout()" in api_js
    assert "setEmail(v)" in api_js

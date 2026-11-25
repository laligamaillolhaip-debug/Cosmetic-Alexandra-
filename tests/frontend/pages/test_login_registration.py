# Форма регистрации
from pathlib import Path


def test_login_page_registers_with_auth_api():
    root = Path(__file__).resolve().parents[3]
    html = (root / "frontend" / "login.html").read_text(encoding="utf-8")

    assert 'id="email"' in html
    assert 'id="password"' in html
    assert 'data-mode="register"' in html
    assert "/api/auth/${mode}" in html
    assert 'window.location.href = "quiz.html"' in html

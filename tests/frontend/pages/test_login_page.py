# Страница входа
from pathlib import Path


def test_login_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "login.html").is_file()

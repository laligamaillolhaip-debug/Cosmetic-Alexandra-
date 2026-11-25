# Страница профиля
from pathlib import Path


def test_profile_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "profile.html").is_file()

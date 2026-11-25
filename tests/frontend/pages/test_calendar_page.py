# Страница календаря
from pathlib import Path


def test_calendar_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "calendar.html").is_file()

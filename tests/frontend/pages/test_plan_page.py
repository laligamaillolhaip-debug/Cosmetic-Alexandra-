# Страница плана
from pathlib import Path


def test_plan_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "plan.html").is_file()

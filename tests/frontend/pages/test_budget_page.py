# Страница бюджета
from pathlib import Path


def test_budget_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "budget.html").is_file()

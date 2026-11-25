# Страница анкеты
from pathlib import Path


def test_quiz_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "quiz.html").is_file()

# Страница чата
from pathlib import Path


def test_chat_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "chat.html").is_file()

# Стартовая страница
from pathlib import Path


def test_index_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "index.html").is_file()

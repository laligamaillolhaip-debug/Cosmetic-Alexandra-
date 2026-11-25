# Страница каталога
from pathlib import Path


def test_catalog_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "catalog.html").is_file()

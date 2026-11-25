# Страница товара
from pathlib import Path


def test_product_page_exists():
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    assert (frontend / "product.html").is_file()

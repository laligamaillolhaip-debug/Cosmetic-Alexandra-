from copy import deepcopy

from app import database, seed_data


def catalog_snapshot():
    with database.get_db() as conn:
        products = conn.execute(
            "SELECT id, name, brand, volume_ml FROM products ORDER BY id"
        ).fetchall()
        prices = conn.execute(
            "SELECT product_id, shop_name, price, source FROM shop_prices "
            "ORDER BY product_id, shop_name"
        ).fetchall()
    return products, prices


def test_seed_catalog_is_isolated_between_temporary_databases(tmp_path, monkeypatch):
    expected_source = deepcopy(seed_data.PRODUCTS)

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "first.db")
    database.init_db()
    first_snapshot = catalog_snapshot()

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "second.db")
    database.init_db()
    second_snapshot = catalog_snapshot()

    assert seed_data.PRODUCTS == expected_source
    assert first_snapshot == second_snapshot
    assert len(first_snapshot[0]) == len(expected_source)

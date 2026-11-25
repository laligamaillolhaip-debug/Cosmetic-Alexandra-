import sys

from app.services.feeds import FeedOffer
from app.services.scraper import PoliteRefusal
from app.tools import check_sources, import_feed, update_prices


def feed_xml(name, vendor, price="1450"):
    return (
        "<yml_catalog><shop><offers>"
        f'<offer id="cli-offer" available="true"><name>{name}</name>'
        f"<vendor>{vendor}</vendor><price>{price}</price><currencyId>RUR</currencyId>"
        "</offer></offers></shop></yml_catalog>"
    )


def read_prices(conn):
    return conn.execute(
        "SELECT product_id, shop_name, price, source FROM shop_prices ORDER BY product_id, shop_name"
    ).fetchall()


def test_import_feed_cli_dry_run_does_not_write_prices(db, tmp_path, monkeypatch, capsys):
    product = db.execute(
        "SELECT * FROM products WHERE id='cleanser-cerave-foaming'"
    ).fetchone()
    before = read_prices(db)
    feed_path = tmp_path / "offers.xml"
    feed_path.write_text(feed_xml(product["name"], product["brand"]), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "import_feed", "--shop", "CLI Test Shop", "--file", str(feed_path), "--dry-run",
    ])

    import_feed.main()

    assert "[dry-run] База не изменялась." in capsys.readouterr().out
    assert read_prices(db) == before


def test_update_prices_cli_dry_run_does_not_write_prices(db, monkeypatch, capsys):
    before = read_prices(db)

    class FakeMarket:
        shop_name = "Wildberries"

        def find_price(self, product):
            return FeedOffer("id", product["name"], product["brand"], 100, "", True)

    monkeypatch.setitem(update_prices.MARKETPLACES, "wildberries", FakeMarket())
    monkeypatch.setattr(sys, "argv", ["update_prices", "--shop", "wildberries", "--limit", "1", "--dry-run"])

    update_prices.main()

    assert "[dry-run] База не изменялась." in capsys.readouterr().out
    assert read_prices(db) == before


def test_update_prices_refusal_after_first_offer_does_not_partially_update(db, monkeypatch, capsys):
    before = read_prices(db)

    class RefusingMarket:
        shop_name = "Wildberries"
        calls = 0

        def find_price(self, product):
            self.calls += 1
            if self.calls == 1:
                return FeedOffer("id", product["name"], product["brand"], 1, "", True)
            raise PoliteRefusal("source refused")

    market = RefusingMarket()
    monkeypatch.setitem(update_prices.MARKETPLACES, "wildberries", market)
    monkeypatch.setattr(sys, "argv", ["update_prices", "--shop", "wildberries", "--limit", "2"])

    update_prices.main()

    output = capsys.readouterr().out
    assert "Цены в базе не тронуты." in output
    assert read_prices(db) == before


def test_update_prices_requires_shop_or_reset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["update_prices"])

    try:
        update_prices.main()
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("CLI should reject missing --shop and --reset")


def test_update_prices_reset_restores_seed_sources_and_clears_urls(db, monkeypatch, capsys):
    db.execute(
        "UPDATE shop_prices SET source='feed', url='https://example.test/item' "
        "WHERE product_id='cleanser-cerave-foaming' AND shop_name='Wildberries'"
    )
    db.commit()
    monkeypatch.setattr(sys, "argv", ["update_prices", "--reset"])

    update_prices.main()

    rows = db.execute(
        "SELECT source, url FROM shop_prices WHERE product_id='cleanser-cerave-foaming'"
    ).fetchall()
    assert "Сброшено записей:" in capsys.readouterr().out
    assert all(row["source"] == "seed" and row["url"] is None for row in rows)


def test_check_sources_cli_uses_only_stubbed_network_calls(monkeypatch, capsys):
    monkeypatch.setattr(check_sources, "TARGETS", [
        ("Allowed source", "https://allowed.example/item"),
        ("Denied source", "https://denied.example/item"),
    ])
    monkeypatch.setattr(check_sources, "tcp_check", lambda _host: "TCP ok")
    monkeypatch.setattr(check_sources, "check_source", lambda url: {
        "allowed": url.startswith("https://allowed"),
        "reason": "stubbed",
    })
    monkeypatch.setattr(
        check_sources.fetcher,
        "get",
        lambda url: type("Result", (), {"text": '{"products": []}', "from_cache": False})(),
    )

    check_sources.main()

    output = capsys.readouterr().out
    assert "Allowed source" in output
    assert "Denied source" in output
    assert "JSON, товаров: 0" in output


def test_import_feed_cli_missing_file_exits_without_database_write(db, tmp_path, monkeypatch):
    before = read_prices(db)
    monkeypatch.setattr(sys, "argv", [
        "import_feed", "--shop", "CLI Test Shop", "--file", str(tmp_path / "missing.xml"),
    ])

    try:
        import_feed.main()
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError("CLI should exit when the feed file does not exist")

    assert read_prices(db) == before

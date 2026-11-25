import xml.etree.ElementTree as ET

import pytest

from app.services.feeds import FeedOffer, import_feed, match_offer, parse_yml


def feed_xml(price="1299", name="Пенка с керамидами и ниацинамидом", vendor="CeraVe Foaming",
             currency="RUR", available="true", include_price=True):
    price_xml = f"<price>{price}</price>" if include_price else ""
    return (
        "<yml_catalog><shop><offers>"
        f'<offer id="offer-1" available="{available}">'
        f"<name>{name}</name><vendor>{vendor}</vendor>{price_xml}"
        f"<currencyId>{currency}</currencyId>"
        "</offer></offers></shop></yml_catalog>"
    )


def make_offer(name, vendor="CeraVe", price=1000, available=True):
    return FeedOffer("id", name, vendor, price, "", available)


def test_parse_yml_supports_decimal_comma_and_fallback_name():
    xml = (
        "<yml_catalog><shop><offers><offer id='123'>"
        "<typePrefix>Пенка</typePrefix><vendor>CeraVe</vendor><model>Foaming</model>"
        "<price>1299,5</price></offer></offers></shop></yml_catalog>"
    )

    offers = parse_yml(xml)

    assert len(offers) == 1
    assert offers[0].name == "Пенка CeraVe Foaming"
    assert offers[0].price == 1300


def test_parse_yml_skips_offer_without_name_or_price():
    xml = (
        "<yml_catalog><shop><offers>"
        "<offer><price>100</price></offer>"
        "<offer><name>Valid name</name></offer>"
        "</offers></shop></yml_catalog>"
    )

    assert parse_yml(xml) == []


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "-Infinity"])
def test_parse_yml_rejects_non_positive_or_non_finite_prices(price):
    assert parse_yml(feed_xml(price=price)) == []


@pytest.mark.parametrize("currency", ["USD", "EUR", "KZT"])
def test_parse_yml_rejects_unsupported_currency(currency):
    assert parse_yml(feed_xml(currency=currency)) == []


def test_parse_yml_preserves_unavailable_offer_for_matching_filter():
    offers = parse_yml(feed_xml(available="false"))

    assert len(offers) == 1
    assert offers[0].available is False
    assert match_offer(
        {"name": "Пенка с керамидами и ниацинамидом", "brand": "CeraVe"},
        offers,
    ) is None


def test_parse_yml_reports_malformed_xml():
    with pytest.raises(ET.ParseError):
        parse_yml("<yml_catalog><offer>")


def test_match_offer_rejects_wrong_brand():
    product = {"name": "Foaming cleanser", "brand": "CeraVe"}

    assert match_offer(product, [make_offer("Foaming cleanser", vendor="OtherBrand")]) is None


def test_match_offer_rejects_name_with_too_few_significant_tokens():
    product = {"name": "Cream", "brand": "CeraVe"}

    assert match_offer(product, [make_offer("Cream")]) is None


def test_match_offer_rejects_different_product_volume():
    product = {"name": "Foaming cleanser", "brand": "CeraVe", "volume_ml": 236}

    assert match_offer(product, [make_offer("Foaming cleanser 473 ml")]) is None


def test_match_offer_ignores_unavailable_offers_and_keeps_first_tie():
    product = {"name": "CeraVe Foaming cleanser", "brand": "CeraVe"}
    unavailable = make_offer("CeraVe Foaming cleanser", available=False)
    first = make_offer("CeraVe Foaming cleanser")
    second = make_offer("CeraVe Foaming cleanser")

    assert match_offer(product, [unavailable, first, second]) is first


def test_import_feed_dry_run_does_not_change_prices(db):
    product = db.execute(
        "SELECT * FROM products WHERE id='cleanser-cerave-foaming'"
    ).fetchone()
    before = db.execute(
        "SELECT product_id, shop_name, price, source FROM shop_prices ORDER BY product_id, shop_name"
    ).fetchall()
    xml = feed_xml(name=product["name"], vendor=product["brand"], price="1450")

    report = import_feed(db, "Unit Test Shop", xml, dry_run=True)

    after = db.execute(
        "SELECT product_id, shop_name, price, source FROM shop_prices ORDER BY product_id, shop_name"
    ).fetchall()
    assert report["dry_run"] is True
    assert report["offers_in_feed"] == 1
    assert any(item["product"] == product["name"] for item in report["matched"])
    assert after == before


def test_import_feed_writes_matched_offer_without_changing_other_shops(db):
    product = db.execute(
        "SELECT * FROM products WHERE id='cleanser-cerave-foaming'"
    ).fetchone()
    before = db.execute(
        "SELECT product_id, shop_name, price, source FROM shop_prices ORDER BY product_id, shop_name"
    ).fetchall()
    xml = feed_xml(name=product["name"], vendor=product["brand"], price="1450")

    report = import_feed(db, "Unit Test Shop", xml)

    inserted = db.execute(
        "SELECT price, source FROM shop_prices WHERE product_id=? AND shop_name=?",
        (product["id"], "Unit Test Shop"),
    ).fetchone()
    after_other_shops = db.execute(
        "SELECT product_id, shop_name, price, source FROM shop_prices "
        "WHERE shop_name != 'Unit Test Shop' ORDER BY product_id, shop_name"
    ).fetchall()
    assert report["dry_run"] is False
    assert inserted["price"] == 1450
    assert inserted["source"] == "feed"
    assert after_other_shops == before


def test_import_feed_updates_existing_shop_price_instead_of_adding_duplicate(db):
    product = db.execute(
        "SELECT * FROM products WHERE id='cleanser-cerave-foaming'"
    ).fetchone()
    xml = feed_xml(name=product["name"], vendor=product["brand"], price="1450")
    before_count = db.execute(
        "SELECT COUNT(*) FROM shop_prices WHERE product_id=? AND shop_name='Wildberries'",
        (product["id"],),
    ).fetchone()[0]

    import_feed(db, "Wildberries", xml)

    rows = db.execute(
        "SELECT price, source FROM shop_prices WHERE product_id=? AND shop_name='Wildberries'",
        (product["id"],),
    ).fetchall()
    assert len(rows) == before_count == 1
    assert rows[0]["price"] == 1450
    assert rows[0]["source"] == "feed"

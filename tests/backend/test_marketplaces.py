import json
from types import SimpleNamespace

import pytest

from app.services import marketplaces
from app.services.scraper import PoliteRefusal


@pytest.mark.parametrize(("raw", "expected"), [
    ({"sizes": [{"price": {"product": 129900}}]}, 1299),
    ({"sizes": [{"price": {"total": 149900}}]}, 1499),
    ({"salePriceU": 189900}, 1899),
    ({"priceU": 219900}, 2199),
    ({"sizes": [], "priceU": 0}, None),
    ({"salePriceU": -100}, None),
    ({"sizes": [{"price": {"product": -100}}]}, None),
    ({}, None),
])
def test_wildberries_extracts_supported_price_shapes(raw, expected):
    assert marketplaces.Wildberries._extract_price(raw) == expected


def test_wildberries_search_retries_malformed_payload_then_parses_products(monkeypatch):
    seen_urls = []
    responses = iter([
        SimpleNamespace(text="{invalid json"),
        SimpleNamespace(text=json.dumps({
            "data": {"products": [{
                "id": 123,
                "name": "Пенка CeraVe",
                "brand": "CeraVe",
                "sizes": [{"price": {"product": 125000}}],
            }]}
        })),
    ])

    def fake_get(url):
        seen_urls.append(url)
        return next(responses)

    monkeypatch.setattr(marketplaces.fetcher, "get", fake_get)

    offers = marketplaces.Wildberries().search("Пенка CeraVe")

    assert len(seen_urls) == 2
    assert "/v13/" in seen_urls[0]
    assert "/v9/" in seen_urls[1]
    assert len(offers) == 1
    assert offers[0].price == 1250
    assert offers[0].offer_id == "123"


def test_wildberries_search_skips_products_without_valid_prices(monkeypatch):
    response = SimpleNamespace(text=json.dumps({
        "products": [
            {"id": 1, "name": "No price", "sizes": []},
            {"id": 2, "name": "Zero price", "priceU": 0},
        ]
    }))
    monkeypatch.setattr(marketplaces.fetcher, "get", lambda _url: response)

    assert marketplaces.Wildberries().search("query") == []


def test_wildberries_search_surfaces_refusal_after_all_versions(monkeypatch):
    monkeypatch.setattr(
        marketplaces.fetcher,
        "get",
        lambda _url: (_ for _ in ()).throw(PoliteRefusal("blocked")),
    )

    with pytest.raises(PoliteRefusal, match="Wildberries недоступен"):
        marketplaces.Wildberries().search("query")


def test_unsupported_marketplace_explains_legal_alternative():
    with pytest.raises(PoliteRefusal, match="Seller API"):
        marketplaces.MARKETPLACES["ozon"].search("query")

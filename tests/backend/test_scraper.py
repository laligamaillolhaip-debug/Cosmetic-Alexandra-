from types import SimpleNamespace

import httpx
import pytest

from app.services import scraper
from app.services.scraper import PoliteFetcher, PoliteRefusal, ResponseCache, RobotsGate


def test_response_cache_ttl_boundary_and_expiry(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(scraper.time, "time", lambda: now[0])
    cache = ResponseCache(tmp_path, ttl=10)
    cache.set("https://example.test/item", "cached")

    now[0] = 109.0
    assert cache.get("https://example.test/item") == "cached"
    now[0] = 110.0
    assert cache.get("https://example.test/item") == "cached"
    now[0] = 111.0
    assert cache.get("https://example.test/item") is None


def test_response_cache_corrupt_json_is_a_cache_miss(tmp_path):
    cache = ResponseCache(tmp_path)
    path = cache._path("https://example.test/item")
    path.write_text("{invalid", encoding="utf-8")

    assert cache.get("https://example.test/item") is None


def test_robots_gate_applies_disallow_and_crawl_delay(monkeypatch):
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url):
            calls.append(url)
            return SimpleNamespace(
                status_code=200,
                text="User-agent: *\nDisallow: /private\nCrawl-delay: 3\n",
            )

    monkeypatch.setattr(scraper.httpx, "Client", lambda **_kwargs: FakeClient())
    gate = RobotsGate()

    assert gate.allowed("https://example.test/public")
    assert not gate.allowed("https://example.test/private/item")
    assert gate.crawl_delay("https://example.test/public") == 3
    assert calls == ["https://example.test/robots.txt"]


def make_fetcher(monkeypatch, cache=None):
    class FakeCache:
        def __init__(self):
            self.body = None
            self.writes = []

        def get(self, _url):
            return self.body

        def set(self, url, body):
            self.writes.append((url, body))

    class FakeRobots:
        def allowed(self, _url):
            return True

        def crawl_delay(self, _url):
            return 1

    if cache is None:
        cache = FakeCache()
    monkeypatch.setattr(scraper, "ResponseCache", lambda: cache)
    fetcher = PoliteFetcher()
    fetcher.robots = FakeRobots()
    fetcher._throttle = lambda *_args: None
    return fetcher, cache


def test_polite_fetcher_robots_denial_sends_no_target_request(monkeypatch):
    fetcher, _cache = make_fetcher(monkeypatch)
    fetcher.robots.allowed = lambda _url: False
    monkeypatch.setattr(
        scraper.httpx,
        "Client",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("network request sent")),
    )

    with pytest.raises(PoliteRefusal, match="robots.txt запрещает"):
        fetcher.get("https://example.test/private")


@pytest.mark.parametrize(("status", "body"), [
    (403, "forbidden"),
    (429, "rate limited"),
    (503, "unavailable"),
    (200, "checking device"),
])
def test_polite_fetcher_blocks_protected_or_refusing_domain(monkeypatch, status, body):
    fetcher, _cache = make_fetcher(monkeypatch)
    requests = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url):
            requests.append(url)
            return SimpleNamespace(status_code=status, text=body)

    monkeypatch.setattr(scraper.httpx, "Client", lambda **_kwargs: FakeClient())
    url = "https://example.test/item"

    with pytest.raises(PoliteRefusal):
        fetcher.get(url)
    with pytest.raises(PoliteRefusal, match="не обращаемся повторно"):
        fetcher.get(url)
    assert len(requests) == 1


def test_polite_fetcher_converts_timeout_to_refusal(monkeypatch):
    fetcher, _cache = make_fetcher(monkeypatch)

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(scraper.httpx, "Client", lambda **_kwargs: FakeClient())

    with pytest.raises(PoliteRefusal, match="сетевая ошибка"):
        fetcher.get("https://example.test/item")


def test_update_price_refusal_preserves_existing_database_price(db, monkeypatch):
    product_id = "cleanser-cerave-foaming"
    shop = "Wildberries"
    before = db.execute(
        "SELECT price FROM shop_prices WHERE product_id=? AND shop_name=?",
        (product_id, shop),
    ).fetchone()["price"]
    monkeypatch.setattr(
        scraper.fetcher,
        "get",
        lambda _url: (_ for _ in ()).throw(PoliteRefusal("source blocked")),
    )

    result = scraper.update_price(db, product_id, shop, "https://example.test", lambda _html: 1)

    after = db.execute(
        "SELECT price FROM shop_prices WHERE product_id=? AND shop_name=?",
        (product_id, shop),
    ).fetchone()["price"]
    assert result["ok"] is False
    assert after == before


def test_update_price_missing_price_preserves_existing_database_price(db, monkeypatch):
    product_id = "cleanser-cerave-foaming"
    shop = "Wildberries"
    before = db.execute(
        "SELECT price FROM shop_prices WHERE product_id=? AND shop_name=?",
        (product_id, shop),
    ).fetchone()["price"]
    monkeypatch.setattr(
        scraper.fetcher,
        "get",
        lambda url: scraper.FetchResult(url, "<html></html>", False),
    )

    result = scraper.update_price(db, product_id, shop, "https://example.test", lambda _html: None)

    after = db.execute(
        "SELECT price FROM shop_prices WHERE product_id=? AND shop_name=?",
        (product_id, shop),
    ).fetchone()["price"]
    assert result["ok"] is False
    assert after == before

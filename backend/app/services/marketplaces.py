"""
Адаптеры к маркетплейсам. Каждый адаптер обязан ходить в сеть только через
PoliteFetcher — то есть с проверкой robots.txt, троттлингом и кэшем.

Статус источников (проверено 07.09.2026 из среды разработки):

  Wildberries    robots.txt разрешает; сайт отдаёт пустой SPA-каркас, но есть
                 публичный JSON-эндпоинт search.wb.ru, которым пользуется их
                 собственный фронтенд. Реализован ниже.
  Ozon           robots.txt разрешает путь /search/, но соединение из тестовой
                 среды не установилось (TCP timeout). Каталог рендерится JS,
                 плюс известна активная защита от ботов. Легальный путь —
                 партнёрская программа / Ozon Seller API.
  Яндекс Маркет  соединение есть, но HTTP 403 на обычный запрос — активная
                 защита. Легальный путь — Yandex Market Partner API или
                 YML-фид магазина.
  Мегамаркет     TCP timeout из тестовой среды; сайт также SPA.
                 Легальный путь — партнёрская программа.

Важно: TCP-таймауты выше — особенность сети, в которой запускалась проверка,
а не приговор источнику. На своей машине прогони `python -m app.tools.check_sources`
и посмотри, что доступно у тебя.

Ни один адаптер не обходит защиту. Если источник отвечает капчей или 403,
PoliteFetcher поднимает PoliteRefusal, и мы просто не берём оттуда цены.
"""
from __future__ import annotations

import json
import urllib.parse

from .feeds import FeedOffer, match_offer
from .scraper import PoliteRefusal, fetcher

# Геокод склада для WB (Москва). Влияет только на выбор витрины.
WB_DEST = -1257786


class Marketplace:
    """Базовый адаптер. shop_name попадает в базу как название магазина."""

    shop_name: str = ""

    def search(self, query: str) -> list[FeedOffer]:
        raise NotImplementedError

    def find_price(self, product: dict) -> FeedOffer | None:
        """Ищет товар на площадке и возвращает подходящее предложение или None."""
        query = f"{product['brand']} {product['name']}"
        offers = self.search(query)
        return match_offer(product, offers)


class Wildberries(Marketplace):
    shop_name = "Wildberries"

    # Эндпоинты менялись (v4 → v13), поэтому пробуем по очереди.
    API_VERSIONS = ("v13", "v9", "v5", "v4")

    def _url(self, version: str, query: str) -> str:
        q = urllib.parse.quote(query)
        return (
            f"https://search.wb.ru/exactmatch/ru/common/{version}/search"
            f"?ab_testing=false&appType=1&curr=rub&dest={WB_DEST}&lang=ru"
            f"&query={q}&resultset=catalog&sort=popular&spp=30&limit=30"
        )

    @staticmethod
    def _extract_price(raw: dict) -> int | None:
        """WB отдаёт цены в копейках, причём в нескольких разных форматах."""
        sizes = raw.get("sizes") or []
        if sizes and isinstance(sizes[0].get("price"), dict):
            kopecks = sizes[0]["price"].get("product") or sizes[0]["price"].get("total")
            if kopecks:
                return int(kopecks / 100)
        for key in ("salePriceU", "priceU"):
            if raw.get(key):
                return int(raw[key] / 100)
        return None

    def search(self, query: str) -> list[FeedOffer]:
        last_error: Exception | None = None
        for version in self.API_VERSIONS:
            try:
                result = fetcher.get(self._url(version, query))
            except PoliteRefusal as e:
                last_error = e
                continue
            try:
                payload = json.loads(result.text)
            except json.JSONDecodeError:
                continue

            products = (payload.get("data") or {}).get("products") or payload.get("products") or []
            if not products:
                continue

            offers = []
            for raw in products:
                price = self._extract_price(raw)
                if not price:
                    continue
                offers.append(FeedOffer(
                    offer_id=str(raw.get("id", "")),
                    name=raw.get("name", ""),
                    vendor=raw.get("brand", ""),
                    price=price,
                    url=f"https://www.wildberries.ru/catalog/{raw.get('id')}/detail.aspx",
                    available=True,
                ))
            if offers:
                return offers

        if last_error:
            raise PoliteRefusal(f"Wildberries недоступен: {last_error}")
        return []


class UnsupportedMarketplace(Marketplace):
    """
    Площадка, с которой мы сознательно не собираем цены автоматически.
    Существует, чтобы причина была видна в отчёте, а не терялась.
    """

    def __init__(self, shop_name: str, reason: str, legal_path: str):
        self.shop_name = shop_name
        self.reason = reason
        self.legal_path = legal_path

    def search(self, query: str) -> list[FeedOffer]:
        raise PoliteRefusal(f"{self.shop_name}: {self.reason}. Легальный путь — {self.legal_path}")


MARKETPLACES: dict[str, Marketplace] = {
    "wildberries": Wildberries(),
    "ozon": UnsupportedMarketplace(
        "Ozon",
        "каталог рендерится JS и стоит защита от ботов",
        "Ozon Seller API или партнёрская программа",
    ),
    "yandex": UnsupportedMarketplace(
        "Яндекс Маркет",
        "обычный запрос получает HTTP 403 (активная защита)",
        "Yandex Market Partner API или YML-фид",
    ),
    "megamarket": UnsupportedMarketplace(
        "Мегамаркет",
        "каталог рендерится JS, прямой доступ не подтверждён",
        "партнёрская программа Мегамаркета",
    ),
}

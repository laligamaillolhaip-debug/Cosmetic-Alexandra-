"""
Импорт цен из товарных фидов (YML — Yandex Market Language).

Это основной легальный путь к ценам: магазин сам публикует фид, а
партнёрские сети (Admitad, ePN, Advcake) дают к нему доступ по договору.
Никакого парсинга страниц, никаких обходов защиты — данные отдают
специально для того, чтобы их использовали.

Как получить фид:
  1. Зарегистрироваться в CPA-сети (для студенческого проекта бесплатно).
  2. Подключиться к программе магазина (у Летуаль она точно есть —
     видно по параметру admitad_uid в их robots.txt).
  3. Скачать XML-фид и скормить его сюда:

     python -m app.tools.import_feed --shop "Летуаль" --file letu.xml

Формат YML (упрощённо):

    <yml_catalog date="...">
      <shop>
        <offers>
          <offer id="123" available="true">
            <url>https://...</url>
            <price>1290</price>
            <currencyId>RUR</currencyId>
            <name>Гель для умывания Effaclar</name>
            <vendor>La Roche-Posay</vendor>
          </offer>
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class FeedOffer:
    offer_id: str
    name: str
    vendor: str
    price: int
    url: str
    available: bool


def parse_yml(xml_text: str) -> list[FeedOffer]:
    """Разбирает YML-фид. Понимает и <name>, и связку <typePrefix>/<model>."""
    root = ET.fromstring(xml_text)
    offers: list[FeedOffer] = []

    for offer in root.iter("offer"):
        price_raw = (offer.findtext("price") or "").strip()
        try:
            price = int(round(float(price_raw.replace(",", "."))))
        except ValueError:
            continue

        name = (offer.findtext("name") or "").strip()
        if not name:
            parts = [offer.findtext("typePrefix"), offer.findtext("vendor"), offer.findtext("model")]
            name = " ".join(p.strip() for p in parts if p and p.strip())
        if not name:
            continue

        offers.append(FeedOffer(
            offer_id=(offer.get("id") or "").strip(),
            name=name,
            vendor=(offer.findtext("vendor") or "").strip(),
            price=price,
            url=(offer.findtext("url") or "").strip(),
            available=(offer.get("available", "true").lower() != "false"),
        ))
    return offers


# Слова, которые есть у половины брендов и товаров — по ним матчить нельзя.
STOPWORDS = {
    "the", "and", "for", "with", "line", "care",
    "для", "или", "как", "что", "мл", "гр", "шт", "уход", "средство",
}

MIN_SCORE = 0.6          # доля слов названия, которая должна совпасть
MIN_OVERLAP_TOKENS = 2   # и минимум столько слов — иначе слишком легко ошибиться


def _normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9 ]+", " ", text)


def _tokens(text: str) -> set[str]:
    return {t for t in _normalize(text).split() if len(t) > 2 and t not in STOPWORDS}


def match_offer(product: dict, offers: list[FeedOffer]) -> FeedOffer | None:
    """
    Сопоставляет товар из нашей базы с предложением из фида.

    Намеренно строгий: лучше не сматчить вообще (и оставить старую цену),
    чем подставить товару цену от другого продукта. Поэтому требуется
    и совпадение бренда, и пересечение минимум по двум значимым словам.
    """
    brand_tokens = _tokens(product["brand"])
    name_tokens = _tokens(product["name"])
    if not name_tokens:
        return None

    best: tuple[float, FeedOffer] | None = None

    for offer in offers:
        if not offer.available:
            continue

        # бренд сверяем с полем vendor, а не со всем названием: иначе
        # случайное общее слово вроде "the" склеивает разные бренды
        if brand_tokens:
            vendor_tokens = _tokens(offer.vendor) or _tokens(offer.name)
            if not (brand_tokens & vendor_tokens):
                continue

        offer_tokens = _tokens(offer.name) | _tokens(offer.vendor)
        overlap = len(name_tokens & offer_tokens)
        score = overlap / len(name_tokens)

        required_overlap = min(MIN_OVERLAP_TOKENS, len(name_tokens))
        if overlap < required_overlap or score < MIN_SCORE:
            continue
        if best is None or score > best[0]:
            best = (score, offer)

    return best[1] if best else None


def import_feed(conn, shop_name: str, xml_text: str, dry_run: bool = False) -> dict:
    """
    Обновляет shop_prices ценами из фида. Возвращает отчёт о том,
    что сматчилось, а что нет — чтобы это можно было проверить глазами.
    """
    from ..database import row_to_dict

    offers = parse_yml(xml_text)
    products = [row_to_dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    now = datetime.now(timezone.utc).isoformat()

    matched, missed = [], []
    for product in products:
        offer = match_offer(product, offers)
        if not offer:
            missed.append(product["name"])
            continue

        matched.append({"product": product["name"], "offer": offer.name, "price": offer.price})
        if dry_run:
            continue

        existing = conn.execute(
            "SELECT id FROM shop_prices WHERE product_id=? AND shop_name=?",
            (product["id"], shop_name),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE shop_prices SET price=?, url=?, updated_at=?, source='feed' WHERE id=?",
                (offer.price, offer.url, now, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO shop_prices (product_id, shop_name, price, url, updated_at, source)
                   VALUES (?,?,?,?,?,'feed')""",
                (product["id"], shop_name, offer.price, offer.url, now),
            )

    return {
        "shop": shop_name,
        "offers_in_feed": len(offers),
        "matched": matched,
        "missed": missed,
        "dry_run": dry_run,
    }

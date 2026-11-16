"""
Обновление цен с маркетплейсов через «вежливый режим».

    python -m app.tools.update_prices --shop wildberries
    python -m app.tools.update_prices --shop wildberries --dry-run
    python -m app.tools.update_prices --shop wildberries --limit 5
    python -m app.tools.update_prices --reset       # вернуть всё к референсным ценам

Каждый запрос проходит проверку robots.txt, троттлинг и кэш.
Если площадка отвечает капчей или 403 — обновление по ней прекращается,
цены в базе остаются прежними. Ничего не «дорисовывается».

Найденные цены помечаются source='scraper' — в интерфейсе такие
подсвечены отдельным цветом, чтобы было видно, что это живые данные.
"""
import argparse
from datetime import datetime, timezone

from ..database import get_db, row_to_dict
from ..services.marketplaces import MARKETPLACES
from ..services.scraper import PoliteRefusal


def reset_prices():
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE shop_prices SET source='seed', url=NULL WHERE source IN ('scraper','feed')"
        )
    print(f"Сброшено записей: {cur.rowcount}. Все цены снова помечены как референсные.")


def main():
    parser = argparse.ArgumentParser(description="Обновление цен с маркетплейсов")
    parser.add_argument("--shop", choices=sorted(MARKETPLACES), help="Площадка")
    parser.add_argument("--limit", type=int, default=0, help="Обновить только N товаров")
    parser.add_argument("--dry-run", action="store_true", help="Показать, но не писать в базу")
    parser.add_argument("--reset", action="store_true", help="Вернуть все цены к референсным")
    args = parser.parse_args()

    if args.reset:
        reset_prices()
        return
    if not args.shop:
        parser.error("укажи --shop или --reset")

    market = MARKETPLACES[args.shop]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        products = [row_to_dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
        if args.limit:
            products = products[:args.limit]

        print(f"\nПлощадка: {market.shop_name}")
        print(f"Товаров к проверке: {len(products)}")
        print("Каждый запрос — не чаще 1 раза в секунду, с проверкой robots.txt\n")

        found = 0
        for product in products:
            label = f"{product['brand']} · {product['name']}"[:52]
            try:
                offer = market.find_price(product)
            except PoliteRefusal as e:
                print(f"\nОстанавливаемся: {e}")
                print("Цены в базе не тронуты.\n")
                return

            if not offer:
                print(f"  — {label:<54} не найдено")
                continue

            found += 1
            print(f"  ✓ {label:<54} {offer.price} ₽")
            print(f"      {offer.name[:64]}")

            if args.dry_run:
                continue

            existing = conn.execute(
                "SELECT id FROM shop_prices WHERE product_id=? AND shop_name=?",
                (product["id"], market.shop_name),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE shop_prices SET price=?, url=?, updated_at=?, source='scraper' WHERE id=?",
                    (offer.price, offer.url, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO shop_prices (product_id, shop_name, price, url, updated_at, source)
                       VALUES (?,?,?,?,?,'scraper')""",
                    (product["id"], market.shop_name, offer.price, offer.url, now),
                )

    print(f"\nНайдено цен: {found} из {len(products)}")
    if args.dry_run:
        print("[dry-run] База не изменялась.")
    print()


if __name__ == "__main__":
    main()

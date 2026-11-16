"""
Импорт цен из YML-фида магазина.

    python -m app.tools.import_feed --shop "Летуаль" --file letu.xml
    python -m app.tools.import_feed --shop "Летуаль" --file letu.xml --dry-run

--dry-run показывает, что сматчилось, но ничего не пишет в базу —
всегда стоит прогнать сначала его и посмотреть глазами.
"""
import argparse
import sys
from pathlib import Path

from ..database import get_db
from ..services.feeds import import_feed


def main():
    parser = argparse.ArgumentParser(description="Импорт цен из YML-фида")
    parser.add_argument("--shop", required=True, help='Название магазина, например "Летуаль"')
    parser.add_argument("--file", required=True, help="Путь к XML-фиду")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, ничего не менять")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Файл не найден: {path}")
        sys.exit(1)

    xml_text = path.read_text(encoding="utf-8", errors="ignore")

    with get_db() as conn:
        report = import_feed(conn, args.shop, xml_text, dry_run=args.dry_run)

    print(f"\nМагазин: {report['shop']}")
    print(f"Предложений в фиде: {report['offers_in_feed']}")
    print(f"Сматчилось товаров: {len(report['matched'])}\n")
    for m in report["matched"]:
        print(f"  ✓ {m['product'][:45]:<47} → {m['price']} ₽")
        print(f"      фид: {m['offer'][:70]}")
    if report["missed"]:
        print(f"\nНе найдено в фиде ({len(report['missed'])}):")
        for name in report["missed"]:
            print(f"  · {name[:60]}")
    if report["dry_run"]:
        print("\n[dry-run] База не изменялась.")


if __name__ == "__main__":
    main()

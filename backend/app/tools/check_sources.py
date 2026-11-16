"""
Диагностика источников цен: что доступно именно с ТВОЕЙ машины.

    python -m app.tools.check_sources

Проверяет по каждому сайту:
  1. отвечает ли хост вообще (TCP),
  2. что говорит robots.txt,
  3. что реально приходит в ответ (контент / капча / 403).

Ничего не парсит и в базу не пишет — только показывает картину.
Результаты могут отличаться от машины к машине: часть площадок
блокирует дата-центры, но пускает обычных домашних провайдеров.
"""
import json
import socket
import time
import urllib.parse

from ..services.scraper import PoliteRefusal, check_source, fetcher

TARGETS = [
    ("Wildberries (сайт)", "https://www.wildberries.ru/catalog/0/search.aspx?search=%D0%BD%D0%B8%D0%B0%D1%86%D0%B8%D0%BD%D0%B0%D0%BC%D0%B8%D0%B4"),
    ("Wildberries (JSON API)", "https://search.wb.ru/exactmatch/ru/common/v13/search"
                               "?ab_testing=false&appType=1&curr=rub&dest=-1257786&lang=ru"
                               "&query=" + urllib.parse.quote("the ordinary ниацинамид") +
                               "&resultset=catalog&sort=popular&spp=30&limit=10"),
    ("Ozon", "https://www.ozon.ru/search/?text=the+ordinary+niacinamide"),
    ("Яндекс Маркет", "https://market.yandex.ru/search?text=the+ordinary"),
    ("Мегамаркет", "https://megamarket.ru/catalog/?q=%D0%BD%D0%B8%D0%B0%D1%86%D0%B8%D0%BD%D0%B0%D0%BC%D0%B8%D0%B4"),
    ("Золотое Яблоко", "https://goldapple.ru/19000175472-niacinamide-10-zinc-1"),
]


def tcp_check(host: str, timeout: float = 8.0) -> str:
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        return f"DNS не резолвится ({e.__class__.__name__})"
    sock = socket.socket()
    sock.settimeout(timeout)
    start = time.time()
    try:
        sock.connect((host, 443))
        return f"TCP ok, {ip}, {time.time() - start:.1f}с"
    except OSError:
        return f"TCP таймаут/отказ, {ip} — вероятно, блокировка на уровне сети"
    finally:
        sock.close()


def main():
    print("\nПроверка источников цен\n" + "=" * 70)

    for label, url in TARGETS:
        host = urllib.parse.urlparse(url).netloc
        print(f"\n{label}  ({host})")
        print(f"  сеть:   {tcp_check(host)}")

        info = check_source(url)
        print(f"  robots: {'разрешает' if info['allowed'] else 'запрещает'} — {info['reason']}")
        if not info["allowed"]:
            continue

        try:
            result = fetcher.get(url)
        except PoliteRefusal as e:
            print(f"  ответ:  ОТКАЗ — {e}")
            continue

        text = result.text
        verdict = f"{len(text)} символов"
        if text.lstrip().startswith("{"):
            try:
                payload = json.loads(text)
                products = (payload.get("data") or {}).get("products") or payload.get("products") or []
                verdict += f", JSON, товаров: {len(products)}"
            except json.JSONDecodeError:
                verdict += ", похоже на JSON, но не разобрался"
        elif "руб" in text.lower() or "₽" in text:
            verdict += ", в HTML есть цены"
        else:
            verdict += ", цен в HTML нет (скорее всего SPA)"
        print(f"  ответ:  OK — {verdict}{' [из кэша]' if result.from_cache else ''}")

    print("\n" + "=" * 70)
    print("Собирать цены имеет смысл только оттуда, где ответ содержит данные.")
    print("Всё остальное — через партнёрские фиды: app/tools/import_feed.py\n")


if __name__ == "__main__":
    main()

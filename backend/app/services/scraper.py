"""
Сбор цен в «вежливом режиме».

Правила зашиты в код, а не в договорённости — нарушить их случайно нельзя:

1. robots.txt проверяется ПЕРЕД каждым запросом (urllib.robotparser).
   Запрещённый путь → запрос не уходит вообще.
2. Crawl-delay из robots.txt соблюдается; если его нет — минимум 1 секунда
   между запросами к одному домену.
3. Ответы кэшируются на диск (по умолчанию 24 часа) — повторный запрос
   за тем же URL не уходит в сеть.
4. User-Agent честный: имя бота, назначение и контакт. Мы не маскируемся
   под обычный браузер.
5. Если сайт отвечает капчей, device-check или 403/429 — домен помечается
   заблокированным до конца сессии, и мы БОЛЬШЕ К НЕМУ НЕ ХОДИМ.
   Обход защиты не реализован и реализован не будет: это ровно та граница,
   за которой начинается неправомерный доступ (ст. 272 УК РФ).

Что проверено вручную (сентябрь 2026):
  • goldapple.ru — robots.txt разрешает каталог, НО сайт встречает бота
    страницей «checking device», а /web/api/v1/settings отдаёт 403.
    Вывод: автоматически цены оттуда получить нельзя. Легальный путь —
    партнёрская программа (CPA-сеть) с товарным фидом, см. services/feeds.py.
  • randewoo.ru — капча даже на /robots.txt. Не трогаем.
  • letu.ru — в robots.txt есть параметр admitad_uid, то есть у магазина
    есть партнёрская программа в Admitad → фид можно получить легально.

Итог: основной путь к ценам — YML-фиды партнёрских программ (feeds.py),
а этот модуль остаётся для тех источников, которые сами разрешают обход
и не ставят защиту.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

CACHE_DIR = Path(__file__).parent.parent / "data" / "http_cache"
CACHE_TTL_SECONDS = 24 * 3600
DEFAULT_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT = 15

# Честное представление. Контакт стоит заменить на свой.
USER_AGENT = (
    "YadroBot/0.1 (educational student project; "
    "price lookup for personal skincare planner; contact: student@example.edu)"
)

# Маркеры того, что нас встретила защита, а не контент.
ANTIBOT_MARKERS = (
    "checking device",
    "проверка браузера",
    "cf-browser-verification",
    "__cf_chl",
    "cf_chl_opt",
    "captcha",
    "камерная проверка",
    "attention required",
    "ddos-guard",
    "variti",
)


class PoliteRefusal(Exception):
    """Запрос не выполнен, потому что это нарушило бы правила. Это не ошибка сети."""


@dataclass
class FetchResult:
    url: str
    text: str
    from_cache: bool


class RobotsGate:
    """Кэширует и применяет robots.txt по доменам."""

    def __init__(self):
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _parser(self, base: str):
        if base in self._parsers:
            return self._parsers[base]
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT},
                              follow_redirects=True) as client:
                resp = client.get(f"{base}/robots.txt")
            if resp.status_code >= 400:
                # robots.txt недоступен — считаем, что правил нет, но ходим осторожно
                rp.parse([])
            else:
                low = resp.text.lower()
                if any(m in low for m in ANTIBOT_MARKERS):
                    # даже robots.txt закрыт защитой — домен для нас закрыт
                    self._parsers[base] = None
                    return None
                rp.parse(resp.text.splitlines())
        except httpx.HTTPError:
            rp.parse([])
        self._parsers[base] = rp
        return rp

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._parser(base)
        if rp is None:
            return False
        return rp.can_fetch(USER_AGENT, url)

    def crawl_delay(self, url: str) -> float:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._parser(base)
        if rp is None:
            return DEFAULT_DELAY_SECONDS
        try:
            delay = rp.crawl_delay(USER_AGENT)
        except (AttributeError, ValueError):
            delay = None
        return max(float(delay or 0), DEFAULT_DELAY_SECONDS)


class ResponseCache:
    def __init__(self, directory: Path = CACHE_DIR, ttl: int = CACHE_TTL_SECONDS):
        self.dir = directory
        self.ttl = ttl
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        return self.dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")

    def get(self, url: str) -> str | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() - payload.get("ts", 0) > self.ttl:
            return None
        return payload.get("body")

    def set(self, url: str, body: str) -> None:
        try:
            self._path(url).write_text(
                json.dumps({"ts": time.time(), "url": url, "body": body}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


class PoliteFetcher:
    """
    Единственная точка выхода в сеть. Всё, что снаружи, обязано ходить через неё.
    """

    def __init__(self):
        self.robots = RobotsGate()
        self.cache = ResponseCache()
        self._last_request: dict[str, float] = {}
        self._blocked: set[str] = set()

    def _throttle(self, host: str, delay: float) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = delay - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.time()

    def get(self, url: str) -> FetchResult:
        host = urlparse(url).netloc

        if host in self._blocked:
            raise PoliteRefusal(
                f"{host}: домен помечен как закрытый защитой в этой сессии — не обращаемся повторно"
            )

        cached = self.cache.get(url)
        if cached is not None:
            return FetchResult(url=url, text=cached, from_cache=True)

        if not self.robots.allowed(url):
            raise PoliteRefusal(f"robots.txt запрещает {url} — запрос не отправлен")

        self._throttle(host, self.robots.crawl_delay(url))

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT,
                                       "Accept-Language": "ru-RU,ru;q=0.9"}) as client:
                resp = client.get(url)
        except httpx.HTTPError as e:
            raise PoliteRefusal(f"сетевая ошибка: {e}") from e

        if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
            self._blocked.add(host)
            raise PoliteRefusal(
                f"{host} ответил {resp.status_code} — считаем это отказом и больше не ходим"
            )

        low = resp.text[:6000].lower()
        if any(marker in low for marker in ANTIBOT_MARKERS):
            self._blocked.add(host)
            raise PoliteRefusal(
                f"{host}: вместо контента отдана проверка на бота. "
                "Обход не выполняется — используйте партнёрский фид (services/feeds.py)"
            )

        self.cache.set(url, resp.text)
        return FetchResult(url=url, text=resp.text, from_cache=False)


fetcher = PoliteFetcher()


def check_source(url: str) -> dict:
    """
    Диагностика источника без сбора данных: можно ли к нему ходить вообще.
    Используется в /api/sources/check, чтобы честно показывать статус в UI.
    """
    host = urlparse(url).netloc
    try:
        allowed = fetcher.robots.allowed(url)
    except Exception as e:  # noqa: BLE001 — диагностика не должна падать
        return {"host": host, "allowed": False, "reason": f"robots.txt недоступен: {e}"}

    if not allowed:
        return {"host": host, "allowed": False, "reason": "запрещено robots.txt или защитой"}
    return {
        "host": host,
        "allowed": True,
        "crawl_delay": fetcher.robots.crawl_delay(url),
        "reason": "robots.txt разрешает; фактический доступ проверяется при первом запросе",
    }


def update_price(conn, product_id: str, shop_name: str, url: str, extract) -> dict:
    """
    Обновляет цену одного товара. `extract` — функция (html) -> int|None,
    своя под каждый магазин. Если источник закрыт, цена в базе не трогается.
    """
    try:
        result = fetcher.get(url)
    except PoliteRefusal as e:
        return {"ok": False, "reason": str(e), "product_id": product_id, "shop": shop_name}

    price = extract(result.text)
    if not price:
        return {"ok": False, "reason": "цена не найдена в разметке", "product_id": product_id, "shop": shop_name}

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE shop_prices SET price=?, url=?, updated_at=?, source='scraper'
           WHERE product_id=? AND shop_name=?""",
        (price, url, now, product_id, shop_name),
    )
    return {"ok": True, "price": price, "product_id": product_id, "shop": shop_name,
            "from_cache": result.from_cache}

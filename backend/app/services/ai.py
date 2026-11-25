"""
Нейросеть через LM Studio или Anthropic.
Текстовые ответы идут через native /api/v1/chat с max_output_tokens;
план — через /v1/chat/completions с JSON Schema и отдельным лимитом
8192 токена, включающим рассуждения thinking-модели. Рассуждения не
показываются в интерфейсе. Итоговый план проверяется в ai_planner.py.
"""
from __future__ import annotations

import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("AI_PROVIDER", "local").strip().lower()

LOCAL_URL = os.getenv("LOCAL_AI_URL", "http://localhost:1234/api/v1/chat")
LOCAL_MODEL = os.getenv("LOCAL_AI_MODEL", "qwen/qwen3-4b-thinking-2507")
LOCAL_TIMEOUT = float(os.getenv("LOCAL_AI_TIMEOUT", "180"))

ANTHROPIC_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-5-20250929")

SYSTEM_PROMPT = (
    "Ты — ИИ-консультант мужского приложения по уходу за кожей «Ядро». "
    "Отвечай по-русски, кратко: не больше 3-4 предложений, без вступлений и "
    "без списков, если о них не просили. Говори прямо, без заискивания и эмодзи. "
    "Опирайся только на переданные факты о коже пользователя, его бюджете и "
    "составе продуктов. Если данных не хватает — так и скажи, не выдумывай. "
    "При серьёзных проблемах кожи (сильное акне, розацеа, экзема) советуй "
    "обратиться к дерматологу."
)

SKIN_TYPE_LABELS = {
    "dry": "сухая", "oily": "жирная", "combination": "комбинированная",
    "sensitive": "чувствительная", "normal": "нормальная",
}
CONCERN_LABELS = {
    "acne": "акне и воспаления", "pores": "расширенные поры",
    "dehydration": "обезвоженность", "sensitivity": "раздражения после бритья",
    "aging": "первые признаки старения", "dullness": "тусклый цвет лица",
}


class AIUnavailable(Exception):
    pass


# ---------------------------------------------------------------- провайдеры

def _strip_reasoning(text: str) -> str:
    """Подстраховка: некоторые модели пишут рассуждения прямо в текст."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _local_complete(system: str, prompt: str) -> str:
    payload = {
        "model": LOCAL_MODEL,
        "system_prompt": system,
        "input": prompt,
        "temperature": 0.4,
        "max_output_tokens": 2048,
        "context_length": 8192,
        "store": False,
    }
    try:
        with httpx.Client(timeout=LOCAL_TIMEOUT) as client:
            resp = client.post(LOCAL_URL, json=payload)
    except httpx.HTTPError as e:
        raise AIUnavailable(
            f"Локальная модель не отвечает ({LOCAL_URL}). "
            "Запущен ли LM Studio и загружена ли модель?"
        ) from e

    if resp.status_code != 200:
        raise AIUnavailable(f"Локальная модель вернула {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    # рассуждения (type="reasoning") пользователю не показываем
    message = "".join(
        block.get("content", "")
        for block in data.get("output", [])
        if block.get("type") == "message"
    )
    message = _strip_reasoning(message)
    if not message:
        raise AIUnavailable("Модель вернула пустой ответ — возможно, не хватило контекста")
    return message


def _anthropic_complete(system: str, prompt: str, max_tokens: int = 400) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or key.startswith("sk-ant-..."):
        raise AIUnavailable(
            "Не задан ANTHROPIC_API_KEY в backend/.env. "
            "Либо впиши ключ, либо переключись на локальную модель: AI_PROVIDER=local"
        )
    try:
        from anthropic import Anthropic, APIError
    except ImportError as e:
        raise AIUnavailable("Пакет anthropic не установлен") from e

    try:
        resp = Anthropic(api_key=key).messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as e:
        raise AIUnavailable(f"Claude временно недоступен: {e}") from e
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def complete(prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 400) -> str:
    if PROVIDER == "anthropic":
        return _anthropic_complete(system, prompt, max_tokens=max_tokens)
    return _local_complete(system, prompt)


def status() -> dict:
    """Проверка связи с моделью — для индикатора в интерфейсе."""
    info = {"provider": PROVIDER,
            "model": ANTHROPIC_MODEL if PROVIDER == "anthropic" else LOCAL_MODEL}
    if PROVIDER == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        ok = bool(key and not key.startswith("sk-ant-..."))
        info.update(ok=ok, detail="Ключ задан" if ok else "Не задан ANTHROPIC_API_KEY")
        return info

    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(LOCAL_URL.replace("/chat", "/models"))
        loaded = [m.get("key") for m in resp.json().get("models", [])]
        ok = resp.status_code == 200 and LOCAL_MODEL in loaded
        info.update(ok=ok, loaded_models=loaded,
                    detail="Локальная модель на связи" if ok else f"Ответ {resp.status_code}")
    except (httpx.HTTPError, ValueError, TypeError):
        info.update(ok=False, detail=f"LM Studio не отвечает на {LOCAL_URL}")
    return info


# ------------------------------------------------------------------ сценарии

def _profile_context(profile: dict) -> str:
    skin = ", ".join(SKIN_TYPE_LABELS.get(s, s) for s in profile["skin_types"])
    concerns = ", ".join(CONCERN_LABELS.get(c, c) for c in profile["concerns"])
    return (
        f"Тип кожи: {skin}. "
        f"Проблемы: {concerns or 'не указаны'}. "
        f"Бюджет на уход: {profile['budget_month']} ₽/мес."
    )


def skin_analysis(profile: dict) -> str:
    return complete(
        f"{_profile_context(profile)}\n\n"
        "Дай короткий разбор: на что делать акцент в уходе этому человеку "
        "и почему, с учётом бюджета. Не больше 3 предложений."
    )


def product_advice(profile: dict, product: dict, plan_products: list[dict]) -> str:
    plan_names = ", ".join(p["name"] for p in plan_products) or "план пока пуст"
    actives = ", ".join(a["name"] for a in product["actives"])
    return complete(
        f"{_profile_context(profile)}\n"
        f"Сейчас в его плане ухода: {plan_names}.\n\n"
        f"Рассматриваемый продукт: {product['name']} ({product['brand']}), "
        f"категория: {product['category']}, активные компоненты: {actives}.\n\n"
        "Ответь: нужен ли этот продукт прямо сейчас, не дублирует ли он что-то "
        "из плана, и стоит ли поискать аналог дешевле. Прямой вывод — первым предложением."
    )


def chat_reply(profile: dict, plan_products: list[dict], history: list[dict], message: str) -> str:
    """
    Локальный эндпоинт одноходовый, поэтому историю переписки сворачиваем
    в текст запроса. Берём последние 6 реплик — иначе не хватит контекста (8k).
    """
    plan_names = ", ".join(p["name"] for p in plan_products) or "план ещё не собран"
    parts = [
        f"[Данные о пользователе]\n{_profile_context(profile)}\n"
        f"Текущий план ухода: {plan_names}."
    ]
    if history:
        lines = [
            f"{'Пользователь' if m['role'] == 'user' else 'Ты'}: {m['content']}"
            for m in history[-6:]
        ]
        parts.append("[Предыдущий разговор]\n" + "\n".join(lines))
    parts.append(f"[Новый вопрос]\n{message}")
    return complete("\n\n".join(parts))


def complete_structured(prompt: str, schema: dict, system: str) -> str:
    """JSON Schema через OpenAI-совместимый endpoint LM Studio."""
    if PROVIDER == "anthropic":
        return complete(prompt, system=system, max_tokens=2000)
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(LOCAL_URL)
    url = urlunsplit((parts.scheme, parts.netloc, "/v1/chat/completions", "", ""))
    payload = {
        "model": LOCAL_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 8192, "stream": False,
        "response_format": {"type": "json_schema", "json_schema": {"name": "daily_skincare_plan", "strict": True, "schema": schema}},
    }
    try:
        # Local generation may take several minutes; only connection and I/O setup are bounded.
        with httpx.Client(timeout=httpx.Timeout(LOCAL_TIMEOUT, read=None)) as client:
            response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIUnavailable("Не удалось получить структурированный план из LM Studio. Текущий план сохранён.") from exc
    if choice.get("finish_reason") == "length":
        raise AIUnavailable("Модель не успела завершить план в пределах ответа. Попробуй повторить подбор.")
    if not content.strip():
        raise AIUnavailable("Локальная модель не вернула готовый план. Текущий план сохранён.")
    return _strip_reasoning(content)

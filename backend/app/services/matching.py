"""
Правило-ориентированный движок подбора. Отвечает за то, что в задаче названо
"ИИ подбирает не только по популярности, но и анализирует состав и бюджет":
здесь это выражено явной, объяснимой оценкой (score), а не чёрным ящиком.
Свободный текст поверх этого (объяснения, чат, совет по товару) генерирует
реальная модель — см. services/ai.py.

Тип кожи — множественный: человек может быть одновременно жирным и
чувствительным, и это меняет подбор (жирной коже нужен контроль себума,
но чувствительной противопоказаны агрессивные кислоты и ретинол).
"""
from __future__ import annotations

CATEGORY_LABELS = {
    "cleanser": "Очищение",
    "toner": "Тоник",
    "exfoliant": "Эксфолиация",
    "serum": "Сыворотки",
    "eye": "Уход за глазами",
    "moisturizer": "Увлажнение",
    "spf": "Защита от солнца",
    "mask": "Маски",
    "balm": "Бальзамы",
}

# План собирается по слотам «время суток × категория», а не «одна категория на
# весь день»: иначе победивший вечерний продукт (например ночной крем) оставлял
# утро вообще без увлажнения. Порядок = очерёдность претензий на бюджет:
# сначала обязательная база утром и вечером, потом активы и допуход.
PLAN_SLOTS = [
    ("morning", "cleanser"), ("evening", "cleanser"),
    ("morning", "moisturizer"), ("evening", "moisturizer"),
    ("morning", "spf"),
    ("evening", "serum"), ("morning", "serum"),
    ("evening", "toner"), ("evening", "exfoliant"),
    ("evening", "eye"), ("morning", "eye"),
]

# Бонус продукту, который уже куплен для другого блока: одним гелем логично
# умываться и утром, и вечером — заодно бюджет не тратится дважды.
REUSE_BONUS = 1.5

# Порядок нанесения — в нём шаги показываются пользователю.
APPLICATION_ORDER = ["cleanser", "toner", "exfoliant", "serum", "eye", "moisturizer", "spf", "mask", "balm"]

# Компоненты, которые для чувствительной кожи — риск, а не плюс.
HARSH_MARKERS = ("ретинол", "кислота", "aha", "bha", "lha", "бензоил")


def cheapest_price(prices: list[dict]) -> dict | None:
    if not prices:
        return None
    return min(prices, key=lambda p: p["price"])


def is_harsh(product: dict) -> bool:
    for active in product["actives"]:
        name = active["name"].lower()
        if any(marker in name for marker in HARSH_MARKERS):
            return True
    return False


def score_product(product: dict, skin_types: set[str], concerns: set[str], price: int) -> float:
    score = 0.0

    skin_overlap = len(skin_types & set(product["skin_types"]))
    score += skin_overlap * 3.0

    concern_overlap = len(concerns & set(product["concerns"]))
    score += concern_overlap * 2.5

    # Чувствительная кожа: агрессивные активы — минус, даже если продукт
    # идеально закрывает другую проблему (например жирность).
    if "sensitive" in skin_types and is_harsh(product):
        score -= 4.5

    score += (product["popularity"] / 100) * 1.5

    # Мягкий штраф за цену, чтобы среди похожих по составу продуктов
    # выигрывал более выгодный по деньгам.
    score -= (price / 1000) * 0.15

    return score


def explain_pick(product: dict, skin_types: set[str], concerns: set[str],
                 price_info: dict, all_prices: list[dict]) -> tuple[str, str]:
    """Возвращает (badge, reason) — почему именно этот продукт попал в план."""
    concern_overlap = concerns & set(product["concerns"])
    is_cheapest = all_prices and price_info["price"] == min(p["price"] for p in all_prices)

    if "sensitive" in skin_types and not is_harsh(product) and "sensitive" in product["skin_types"]:
        return "gentle", "Мягкая формула — без агрессивных кислот и ретинола"
    if concern_overlap:
        actives = ", ".join(a["name"] for a in product["actives"][:2])
        return "match", f"Подобрано по составу: {actives}"
    if is_cheapest and len(all_prices) > 1:
        return "value", "Лучшая цена среди аналогов с похожим действием"
    if product["popularity"] >= 85:
        return "popular", "Один из самых востребованных вариантов в категории"
    return "match", "Подходит под твой тип кожи"


def build_plan(profile: dict, products: list[dict], prices_by_product: dict[str, list[dict]]) -> dict:
    """
    Возвращает {"plan": {"morning": [...], "evening": [...]}, "spent": int, "budget": int}.

    Заполняет слоты из PLAN_SLOTS по очереди, укладываясь в бюджет. Продукт,
    уже купленный для другого блока, повторно бюджет не тратит — поэтому
    утреннее и вечернее очищение обычно закрываются одним средством.
    """
    skin_types = set(profile["skin_types"])
    concerns = set(profile["concerns"])
    budget = profile["budget_month"]
    spent = 0
    plan = {"morning": [], "evening": []}
    bought: dict[str, dict] = {}  # product_id -> price_info, что уже оплачено

    for time_of_day, category in PLAN_SLOTS:
        scored = []
        for p in products:
            if p["category"] != category:
                continue
            if p["time_of_day"] not in ("both", time_of_day):
                continue
            # подходит по типу кожи ИЛИ закрывает заявленную проблему
            if not (skin_types & set(p["skin_types"])) and not (concerns & set(p["concerns"])):
                continue
            cheapest = cheapest_price(prices_by_product.get(p["id"], []))
            if not cheapest:
                continue

            score = score_product(p, skin_types, concerns, cheapest["price"])
            if p["id"] in bought:
                score += REUSE_BONUS
            scored.append((score, p, cheapest))

        if not scored:
            continue
        scored.sort(key=lambda t: t[0], reverse=True)

        def slot_cost(product_id: str, price_info: dict) -> int:
            return 0 if product_id in bought else price_info["price"]

        chosen = None
        for _, p, price_info in scored:
            if spent + slot_cost(p["id"], price_info) <= budget:
                chosen = (p, price_info)
                break
        if chosen is None:
            # даже лучший по цене не влезает — пробуем самый дешёвый вариант
            for _, p, price_info in sorted(scored, key=lambda t: t[2]["price"]):
                if spent + slot_cost(p["id"], price_info) <= budget:
                    chosen = (p, price_info)
                    break
        if chosen is None:
            continue

        product, price_info = chosen
        spent += slot_cost(product["id"], price_info)
        bought[product["id"]] = price_info

        all_prices = prices_by_product.get(product["id"], [])
        badge, reason = explain_pick(product, skin_types, concerns, price_info, all_prices)

        plan[time_of_day].append({
            "product": product,
            "price": price_info,
            "badge": badge,
            "reason": reason,
            "category_label": CATEGORY_LABELS.get(category, category),
        })

    # слоты заполнялись в порядке приоритета бюджета, а показывать нужно
    # в порядке нанесения: сначала очищение, SPF — последним
    for items in plan.values():
        items.sort(key=lambda i: APPLICATION_ORDER.index(i["product"]["category"])
                   if i["product"]["category"] in APPLICATION_ORDER else 99)

    return {"plan": plan, "spent": spent, "budget": budget}

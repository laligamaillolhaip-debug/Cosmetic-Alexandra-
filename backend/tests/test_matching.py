import pytest
from app.services.matching import (
    score_product,
    is_harsh,
    explain_pick,
    cheapest_price,
    build_plan
)

def make_product(
    id="p1",
    category="cleanser",
    time_of_day="both",
    skin_types=("oily",),
    concerns=("acne",),
    popularity=50,
    actives=()
):
    return {
        "id": id,
        "name": f"Product {id}",
        "category": category,
        "time_of_day": time_of_day,
        "skin_types": list(skin_types),
        "concerns": list(concerns),
        "popularity": popularity,
        # actives всегда список словарей!
        "actives": [{"name": n} for n in actives],
    }


# ─────────────────────── score_product ───────────────────────
@pytest.mark.parametrize("popularity, price, expected", [
    (50, 1000, 6.1),
    (0, 1000, 5.35),
    (100, 1000, 6.85),
    (50, 0, 6.25),
])
def test_score_product_formula(popularity, price, expected):
    product = make_product(popularity=popularity)
    result = score_product(product, {"oily"}, {"acne"}, price)
    assert result == pytest.approx(expected)

def test_score_product_sensitive_harsh_penalty():
    
    product = make_product(
        skin_types=("sensitive",), 
        concerns=("acne",), 
        actives=["ретинол"]
    )
    result = score_product(product, {"sensitive"}, {"acne"}, 1000)
    
    
    assert result == pytest.approx(1.6)

def test_score_product_empty_sets():
    product = make_product()
    result = score_product(product, set(), set(), 1000)
    assert result == pytest.approx(0.6)


# ─────────────────────── is_harsh ───────────────────────
@pytest.mark.parametrize("active_name, expected", [
    ("ретинол", True),
    ("салициловая кислота", True),
    ("гликолевая кислота", True),
    ("AHA", True),
    ("витамин С", False),
])
def test_is_harsh(active_name, expected):
    product = make_product(actives=[active_name])
    assert is_harsh(product) is expected


@pytest.mark.xfail(reason="Дефект D-02: слово 'кислота' в HARSH_MARKERS ловит безопасную гиалуроновую кислоту")
def test_is_harsh_hyaluronic_acid_bug():
    product = make_product(actives=["гиалуроновая кислота"])
    # Ожидаем, что она НЕ агрессивна (по ТЗ)
    assert is_harsh(product) is False


# ─────────────────────── cheapest_price ───────────────────────
def test_cheapest_price():
    prices = [
        {"shop_name": "Shop1", "price": 1500},
        {"shop_name": "Shop2", "price": 1000},
        {"shop_name": "Shop3", "price": 1200},
    ]
    result = cheapest_price(prices)
    assert result["price"] == 1000
    assert result["shop_name"] == "Shop2"

def test_cheapest_price_empty():
    assert cheapest_price([]) is None


# ─────────────────────── explain_pick ───────────────────────
def test_explain_pick_gentle():
    product = make_product(skin_types=("sensitive",), actives=[])
    price_info = {"price": 1000}
    all_prices = [price_info]
    badge, reason = explain_pick(product, {"sensitive"}, set(), price_info, all_prices)
    assert badge == "gentle"

def test_explain_pick_match_concern():
    product = make_product(concerns=("acne",), actives=["салициловая кислота"])
    price_info = {"price": 2000}
    all_prices = [price_info, {"price": 3000}]
    badge, reason = explain_pick(product, {"dry"}, {"acne"}, price_info, all_prices)
    assert badge == "match"
    assert "составу" in reason

def test_explain_pick_value():
    product = make_product(concerns=(), skin_types=("dry",))
    price_info = {"price": 1000}
    all_prices = [{"price": 1000}, {"price": 1500}] # Минимальная цена
    badge, reason = explain_pick(product, {"dry"}, set(), price_info, all_prices)
    assert badge == "value"

def test_explain_pick_popular():
    product = make_product(popularity=85, concerns=(), skin_types=("dry",))
    price_info = {"price": 2000}
    all_prices = [{"price": 2000}, {"price": 1000}] # Не минимальная
    badge, reason = explain_pick(product, {"dry"}, set(), price_info, all_prices)
    assert badge == "popular"

def test_explain_pick_fallback_match_skin_type():
    product = make_product(popularity=84, concerns=(), skin_types=("dry",))
    price_info = {"price": 2000}
    all_prices = [{"price": 2000}, {"price": 1000}]
    badge, reason = explain_pick(product, {"dry"}, set(), price_info, all_prices)
    assert badge == "match"
    assert "тип кожи" in reason


# ─────────────────────── build_plan ───────────────────────
def test_build_plan_empty_products():
    profile = {"skin_types": ["normal"], "concerns": [], "budget_month": 300}
    result = build_plan(profile, [], {})
    assert result["spent"] == 0
    assert result["plan"]["morning"] == []
    assert result["plan"]["evening"] == []

def test_build_plan_budget_not_enough():
    # Очищение стоит 500, а бюджет 499
    product = make_product(category="cleanser")
    prices = {product["id"]: [{"price": 500}]}
    profile = {"skin_types": ["oily"], "concerns": ["acne"], "budget_month": 499}
    result = build_plan(profile, [product], prices)
    assert result["plan"]["morning"] == []
    assert result["spent"] == 0

def test_build_plan_reuse_bonus():
    # Один товар для утра и вечера (time_of_day="both")
    product = make_product(category="cleanser", time_of_day="both")
    prices = {product["id"]: [{"price": 1000}]}
    profile = {"skin_types": ["oily"], "concerns": [], "budget_month": 2000}
    
    result = build_plan(profile, [product], prices)
    
    # Товар попал и в morning, и в evening
    assert len(result["plan"]["morning"]) == 1
    assert len(result["plan"]["evening"]) == 1
    # Но потрачен 1000 (один раз), так как REUSE_BONUS
    assert result["spent"] == 1000
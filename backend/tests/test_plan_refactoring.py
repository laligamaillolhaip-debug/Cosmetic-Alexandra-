import pytest
from app.services import matching, ai_planner


def product(pid, category="cleanser", price=500):
    item = {"id": pid, "name": pid, "brand": "Brand", "category": category,
            "time_of_day": "morning" if category == "spf" else "both",
            "skin_types": ["normal"], "concerns": [], "actives": [], "popularity": 50}
    return item, {"price": price, "shop_name": "Shop"}


@pytest.mark.parametrize("budget, expected", [(0, 0), (499, 0), (500, 500), (1000, 500)])
def test_reused_product_respects_exact_budget(budget, expected):
    item, price = product("cleanser")
    result = matching.build_plan({"skin_types": ["normal"], "concerns": [], "budget_month": budget},
                                 [item], {item["id"]: [price]})
    assert result["spent"] == expected
    assert sum(map(len, result["plan"].values())) == (2 if expected else 0)


def test_equal_scores_keep_catalog_order_and_builds_do_not_share_purchases():
    first, first_price = product("first")
    second, second_price = product("second")
    profile = {"skin_types": ["normal"], "concerns": [], "budget_month": 500}
    prices = {"first": [first_price], "second": [second_price]}
    result = matching.build_plan(profile, [first, second], prices)
    assert result["plan"]["morning"][0]["product"]["id"] == "first"
    assert matching.build_plan({**profile, "budget_month": 0}, [first, second], prices)["spent"] == 0
    assert matching.build_plan(profile, [first, second], prices) == result


def selection_example():
    pairs = [product(cat, cat, price) for cat, price in [("cleanser", 100), ("moisturizer", 200), ("spf", 300)]]
    options = [{"product": item, "price": price} for item, price in pairs]
    selection = {"morning": [{"id": cat, "reason": "Подходит"} for cat in ["cleanser", "moisturizer", "spf"]],
                 "evening": [{"id": cat, "reason": "Подходит"} for cat in ["cleanser", "moisturizer"]], "summary": "Уход"}
    profile = {"skin_types": ["normal"], "concerns": [], "budget_month": 600}
    return selection, profile, options


@pytest.mark.parametrize("field, length, valid", [("reason", 350, True), ("reason", 351, False),
                                                 ("summary", 900, True), ("summary", 901, False)])
def test_model_text_length_boundaries_are_preserved(field, length, valid):
    selection, profile, options = selection_example()
    if field == "reason":
        selection["morning"][0][field] = "x" * length
    else:
        selection[field] = "x" * length
    if valid:
        assert ai_planner.validate_selection(selection, profile, options)["spent"] == 600
    else:
        with pytest.raises(ai_planner.InvalidPlan):
            ai_planner.validate_selection(selection, profile, options)


def test_invalid_product_is_reported_before_reason_and_budget():
    selection, profile, options = selection_example()
    selection["morning"][0] = {"id": "missing", "reason": ""}
    profile["budget_month"] = 0
    with pytest.raises(ai_planner.InvalidPlan, match="Выбран отсутствующий или неподходящий товар"):
        ai_planner.validate_selection(selection, profile, options)

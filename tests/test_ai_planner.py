import json
import pytest
from app.services import ai, ai_planner
from app.database import get_db
from app.routers.products import load_products_with_prices


def example():
    products = []
    prices = {}
    for category, price, tod in [("cleanser", 100, "both"), ("moisturizer", 200, "both"), ("spf", 300, "morning")]:
        products.append({"id": category, "name": category, "brand": "Brand", "category": category, "time_of_day": tod, "skin_types": ["normal", "sensitive"], "concerns": [], "actives": [], "popularity": 50})
        prices[category] = [{"price": price, "product_id": category, "shop_name": "Shop"}]
    profile = {"skin_types": ["normal"], "concerns": [], "budget_month": 1000}
    selection = {"morning": [{"id": k, "reason": "Подходит по анкете"} for k in ["cleanser", "moisturizer", "spf"]], "evening": [{"id": k, "reason": "Подходит по анкете"} for k in ["cleanser", "moisturizer"]], "summary": "Базовый план"}
    return profile, products, prices, selection


def test_ai_plan_counts_each_purchase_once_and_uses_database_prices():
    p, products, prices, selection = example()
    selection["morning"][0]["price"] = 1
    result = ai_planner.validate_selection(selection, p, ai_planner.candidates(p, products, prices))
    assert result["spent"] == 600
    assert result["plan"]["morning"][-1]["product"]["category"] == "spf"


@pytest.mark.parametrize("case", ["unknown", "evening_spf", "duplicate", "missing_base", "over_budget", "empty_reason"])
def test_invalid_model_selection_is_rejected(case):
    p, products, prices, selection = example()
    if case == "unknown": selection["morning"][0]["id"] = "invented"
    elif case == "evening_spf": selection["evening"].append({"id": "spf", "reason": "test"})
    elif case == "duplicate": selection["morning"].append(selection["morning"][0])
    elif case == "missing_base": selection["morning"].pop()
    elif case == "over_budget": p["budget_month"] = 599
    elif case == "empty_reason": selection["morning"][0]["reason"] = ""
    with pytest.raises(ai_planner.InvalidPlan):
        ai_planner.validate_selection(selection, p, ai_planner.candidates(p, products, prices))


def test_sensitive_candidates_exclude_exfoliating_acids_but_keep_hyaluronic():
    p, products, prices, selection = example()
    p["skin_types"] = ["sensitive"]
    products[0]["actives"] = [{"name": "салициловая кислота"}]
    products[1]["actives"] = [{"name": "гиалуроновая кислота"}]
    ids = {x["product"]["id"] for x in ai_planner.candidates(p, products, prices)}
    assert "cleanser" not in ids and "moisturizer" in ids


def test_impossible_budget_does_not_call_model(monkeypatch):
    p, products, prices, _ = example()
    p["budget_month"] = 300
    def unexpected(*args, **kwargs):
        pytest.fail("Model must not be called for an impossible base budget")
    monkeypatch.setattr(ai, "complete_structured", unexpected)
    with pytest.raises(ai_planner.InvalidPlan, match="600"):
        ai_planner.generate(p, products, prices)


def test_generation_retries_invalid_response_without_invented_products(monkeypatch):
    p, products, prices, selection = example()
    replies = iter(['{"morning":[],"evening":[],"summary":"bad"}', json.dumps(selection)])
    monkeypatch.setattr(ai, "complete_structured", lambda *args, **kwargs: next(replies))
    result = ai_planner.generate(p, products, prices)
    assert result["spent"] == 600


def seeded_proposal(profile, products, prices):
    options = ai_planner.candidates(profile, products, prices)
    selection = {"summary": "Проверенный план"}
    for tod, cats in ai_planner.BASE.items():
        selection[tod] = [{"id": min([o for o in options if o["product"]["category"] == cat and ai_planner.fits_time(o["product"], tod)], key=lambda o: o["price"]["price"])["product"]["id"], "reason": "Выбрано из каталога"} for cat in cats]
    return ai_planner.validate_selection(selection, profile, options)


@pytest.fixture
def draft_profile(client, test_user, monkeypatch):
    response = client.post("/api/profile", json={"skin_types": ["normal"], "concerns": [], "budget_month": 100000})
    assert response.status_code == 200
    monkeypatch.setattr(ai_planner, "generate", seeded_proposal)
    return response.json()["profile_id"]


def test_draft_does_not_change_plan_and_apply_persists_it(client, draft_profile):
    pid = draft_profile
    before = client.get(f"/api/plan/{pid}").json()
    response = client.post(f"/api/plan/{pid}/ai-draft")
    assert response.status_code == 200
    assert client.get(f"/api/plan/{pid}").json() == before
    draft_id = response.json()["draft_id"]
    applied = client.post(f"/api/plan/{pid}/ai-draft/{draft_id}/apply")
    assert applied.status_code == 200
    result = applied.json()
    assert result["profile"]["plan_source"] == "ai"
    assert result["profile"]["plan_summary"] == "Проверенный план"
    assert result["spent"] == response.json()["spent"]
    assert all(i["badge"] == "ai" for items in result["plan"].values() for i in items)
    assert client.post(f"/api/plan/{pid}/ai-draft/{draft_id}/apply").status_code == 404


@pytest.mark.parametrize("change", ["budget", "catalog", "plan"])
def test_stale_draft_is_rejected(client, draft_profile, change):
    pid = draft_profile
    draft = client.post(f"/api/plan/{pid}/ai-draft").json()
    with get_db() as conn:
        if change == "budget": conn.execute("UPDATE profiles SET budget_month=90000 WHERE id=?", (pid,))
        elif change == "catalog": conn.execute("UPDATE shop_prices SET price=price+1")
        else: conn.execute("UPDATE plan_items SET reason='changed' WHERE profile_id=?", (pid,))
    before = client.get(f"/api/plan/{pid}").json()
    assert client.post(f"/api/plan/{pid}/ai-draft/{draft['draft_id']}/apply").status_code == 409
    assert client.get(f"/api/plan/{pid}").json() == before


def test_model_outage_preserves_existing_plan(client, draft_profile, monkeypatch):
    pid = draft_profile
    before = client.get(f"/api/plan/{pid}").json()
    def offline(*args): raise ai.AIUnavailable("offline")
    monkeypatch.setattr(ai_planner, "generate", offline)
    assert client.post(f"/api/plan/{pid}/ai-draft").status_code == 503
    assert client.get(f"/api/plan/{pid}").json() == before


def test_other_user_cannot_generate_or_apply_owner_draft(client, draft_profile):
    pid = draft_profile
    draft = client.post(f"/api/plan/{pid}/ai-draft").json()
    client.post("/api/auth/register", json={"email":"other@example.com","password":"secret123"})
    assert client.post(f"/api/plan/{pid}/ai-draft").status_code == 403
    assert client.post(f"/api/plan/{pid}/ai-draft/{draft['draft_id']}/apply").status_code == 403

def test_generated_claims_are_not_presented_as_product_facts():
    p, products, prices, selection = example()
    selection["morning"][0]["reason"] = "Гарантированно лечит акне без раздражения"
    result = ai_planner.validate_selection(selection, p, ai_planner.candidates(p, products, prices))
    assert "Гарантированно" not in result["plan"]["morning"][0]["reason"]
    assert "Тип кожи:" in result["plan"]["morning"][0]["reason"]


def test_pending_draft_can_be_reloaded_but_stale_one_is_hidden(client, draft_profile):
    pid = draft_profile
    assert client.get(f"/api/plan/{pid}/ai-draft").json() == {"draft": None}
    draft = client.post(f"/api/plan/{pid}/ai-draft").json()
    pending = client.get(f"/api/plan/{pid}/ai-draft").json()["draft"]
    assert pending["draft_id"] == draft["draft_id"]
    with get_db() as conn:
        conn.execute("UPDATE profiles SET budget_month=90000 WHERE id=?", (pid,))
    assert client.get(f"/api/plan/{pid}/ai-draft").json() == {"draft": None}


def test_dismissed_draft_does_not_return_after_reload(client, draft_profile):
    pid = draft_profile
    before = client.get(f"/api/plan/{pid}").json()
    draft = client.post(f"/api/plan/{pid}/ai-draft").json()
    response = client.delete(f"/api/plan/{pid}/ai-draft/{draft['draft_id']}")
    assert response.status_code == 200
    assert client.get(f"/api/plan/{pid}/ai-draft").json() == {"draft": None}
    assert client.get(f"/api/plan/{pid}").json() == before

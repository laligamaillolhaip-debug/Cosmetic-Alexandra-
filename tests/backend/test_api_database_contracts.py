import json
import uuid
from datetime import date
from unittest.mock import patch

from app.database import get_db
from app.services.ai import AIUnavailable
from tests.backend.test_calendar_router import create_test_profile_and_product


def create_foreign_profile():
    user_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
            (user_id, f"{user_id}@example.test", "hash", date.today().isoformat()),
        )
        conn.execute(
            "INSERT INTO profiles (id, user_id, skin_types, concerns, budget_month, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (profile_id, user_id, '["dry"]', "[]", 5000, date.today().isoformat()),
        )
    return profile_id


def test_profile_scoped_api_requires_authentication(client):
    profile_id = "private-profile"
    responses = [
        client.get(f"/api/profile/{profile_id}"),
        client.get(f"/api/plan/{profile_id}"),
        client.get(f"/api/calendar/{profile_id}"),
        client.get(f"/api/favorites/{profile_id}"),
        client.get(f"/api/chat/{profile_id}/history"),
    ]

    assert [response.status_code for response in responses] == [401] * len(responses)


def test_all_profile_routes_reject_foreign_owner(client, test_user):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id = create_foreign_profile()
    profile = {"skin_types": ["dry"], "concerns": [], "budget_month": 5000}
    requests = [
        client.get(f"/api/profile/{profile_id}"),
        client.put(f"/api/profile/{profile_id}", json=profile),
        client.post(f"/api/profile/{profile_id}/analysis"),
        client.get(f"/api/plan/{profile_id}"),
        client.post(f"/api/plan/{profile_id}/items", json={
            "product_id": "cleanser-effaclar", "time_of_day": "morning",
        }),
        client.delete(f"/api/plan/{profile_id}/items/1"),
        client.post(f"/api/plan/{profile_id}/reorder", json={
            "time_of_day": "morning", "item_ids": [],
        }),
        client.post(f"/api/plan/{profile_id}/ai-draft"),
        client.get(f"/api/plan/{profile_id}/ai-draft"),
        client.delete(f"/api/plan/{profile_id}/ai-draft/unknown"),
        client.post(f"/api/plan/{profile_id}/ai-draft/unknown/apply"),
        client.get(f"/api/calendar/{profile_id}"),
        client.post(f"/api/calendar/{profile_id}/toggle", json={
            "date": date.today().isoformat(),
            "time_of_day": "morning",
            "product_id": "cleanser-effaclar",
            "done": True,
        }),
        client.get(f"/api/favorites/{profile_id}"),
        client.post(f"/api/favorites/{profile_id}", json={"product_id": "cleanser-effaclar"}),
        client.delete(f"/api/favorites/{profile_id}/cleanser-effaclar"),
        client.get(f"/api/chat/{profile_id}/history"),
        client.post(f"/api/chat/{profile_id}", json={"message": "Hello"}),
    ]

    assert [response.status_code for response in requests] == [403] * len(requests)


def test_duplicate_favorite_requests_create_one_database_row(client, test_user):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, product_id = create_test_profile_and_product(test_user["email"])

    first = client.post(f"/api/favorites/{profile_id}", json={"product_id": product_id})
    second = client.post(f"/api/favorites/{profile_id}", json={"product_id": product_id})
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE profile_id=? AND product_id=?",
            (profile_id, product_id),
        ).fetchone()[0]

    assert first.status_code == second.status_code == 200
    assert count == 1


def test_adding_existing_plan_item_is_idempotent(client, test_user):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, product_id = create_test_profile_and_product(test_user["email"])

    response = client.post(f"/api/plan/{profile_id}/items", json={
        "product_id": product_id, "time_of_day": "morning",
    })
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM plan_items WHERE profile_id=? AND product_id=? AND time_of_day='morning'",
            (profile_id, product_id),
        ).fetchone()[0]

    assert response.status_code == 200
    assert response.json()["already"] is True
    assert count == 1


def test_repeated_profile_creation_updates_single_account_profile(client, test_user, monkeypatch):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    monkeypatch.setattr(
        "app.routers.profile.build_plan",
        lambda *_args: {"plan": {"morning": [], "evening": []}, "spent": 0},
    )
    first = client.post("/api/profile", json={
        "skin_types": ["dry"], "concerns": ["acne"], "budget_month": 4000,
    })
    second = client.post("/api/profile", json={
        "skin_types": ["oily"], "concerns": ["pores"], "budget_month": 7000,
    })

    with get_db() as conn:
        profiles = conn.execute(
            "SELECT id, skin_types, concerns, budget_month FROM profiles "
            "WHERE user_id=(SELECT id FROM users WHERE email=?)",
            (test_user["email"],),
        ).fetchall()

    assert first.status_code == second.status_code == 200
    assert first.json()["profile_id"] == second.json()["profile_id"]
    assert len(profiles) == 1
    assert json.loads(profiles[0]["skin_types"]) == ["oily"]
    assert json.loads(profiles[0]["concerns"]) == ["pores"]
    assert profiles[0]["budget_month"] == 7000


def test_ai_advice_returns_mocked_provider_result(client, test_user, monkeypatch):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, _product_id = create_test_profile_and_product(test_user["email"])
    calls = []

    def fake_advice(profile, product, plan_products):
        calls.append((profile, product, plan_products))
        return "Mock advice"

    monkeypatch.setattr("app.routers.products.ai.product_advice", fake_advice)
    response = client.post(
        "/api/products/cleanser-effaclar/ai-advice",
        json={"profile_id": profile_id},
    )

    assert response.status_code == 200
    assert response.json() == {"advice": "Mock advice"}
    assert calls[0][0]["id"] == profile_id
    assert calls[0][1]["id"] == "cleanser-effaclar"


def test_ai_advice_does_not_disclose_foreign_profile(client, test_user, monkeypatch):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    foreign_profile_id = create_foreign_profile()
    advice = []
    monkeypatch.setattr(
        "app.routers.products.ai.product_advice",
        lambda *_args: advice.append("called"),
    )

    response = client.post(
        "/api/products/cleanser-effaclar/ai-advice",
        json={"profile_id": foreign_profile_id},
    )

    assert response.status_code == 404
    assert advice == []


def test_ai_advice_provider_failure_returns_service_unavailable(client, test_user, monkeypatch):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, _product_id = create_test_profile_and_product(test_user["email"])
    monkeypatch.setattr(
        "app.routers.products.ai.product_advice",
        lambda *_args: (_ for _ in ()).throw(AIUnavailable("provider offline")),
    )

    response = client.post(
        "/api/products/cleanser-effaclar/ai-advice",
        json={"profile_id": profile_id},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "provider offline"


def test_retake_profile_preserves_favorites_calendar_and_chat(client, test_user, monkeypatch):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    client.post(f"/api/favorites/{profile_id}", json={"product_id": product_id})
    client.post(f"/api/calendar/{profile_id}/toggle", json={
        "date": date.today().isoformat(),
        "time_of_day": "morning",
        "product_id": product_id,
        "done": True,
    })
    monkeypatch.setattr("app.services.ai.chat_reply", lambda *_args: "Saved reply")
    client.post(f"/api/chat/{profile_id}", json={"message": "Saved question"})
    with get_db() as conn:
        conn.execute("UPDATE profiles SET analysis='stale analysis' WHERE id=?", (profile_id,))

    monkeypatch.setattr(
        "app.routers.profile.build_plan",
        lambda *_args: {"plan": {"morning": [], "evening": []}, "spent": 0},
    )
    response = client.put(f"/api/profile/{profile_id}", json={
        "skin_types": ["oily"],
        "concerns": ["pores"],
        "budget_month": 7000,
    })

    with get_db() as conn:
        profile = conn.execute(
            "SELECT skin_types, concerns, budget_month, analysis FROM profiles WHERE id=?",
            (profile_id,),
        ).fetchone()
        favorites = conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE profile_id=?", (profile_id,),
        ).fetchone()[0]
        completed_steps = conn.execute(
            "SELECT COUNT(*) FROM routine_log WHERE profile_id=? AND done=1", (profile_id,),
        ).fetchone()[0]
        messages = conn.execute(
            "SELECT role, content FROM chat_messages WHERE profile_id=? ORDER BY id", (profile_id,),
        ).fetchall()
        profiles_for_user = conn.execute(
            "SELECT COUNT(*) FROM profiles WHERE user_id=(SELECT id FROM users WHERE email=?)",
            (test_user["email"],),
        ).fetchone()[0]

    assert response.status_code == 200
    assert json.loads(profile["skin_types"]) == ["oily"]
    assert json.loads(profile["concerns"]) == ["pores"]
    assert profile["budget_month"] == 7000
    assert profile["analysis"] is None
    assert favorites == 1
    assert completed_steps == 1
    assert [(row["role"], row["content"]) for row in messages] == [
        ("user", "Saved question"),
        ("assistant", "Saved reply"),
    ]
    assert profiles_for_user == 1


def test_chat_ai_failure_does_not_persist_partial_conversation(client, test_user):
    client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    })
    profile_id, _product_id = create_test_profile_and_product(test_user["email"])
    with patch("app.services.ai.chat_reply", side_effect=AIUnavailable("model offline")):
        response = client.post(f"/api/chat/{profile_id}", json={"message": "Question"})

    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE profile_id=?", (profile_id,),
        ).fetchone()[0]

    assert response.status_code == 503
    assert count == 0


def test_product_price_filter_includes_exact_limit_and_excludes_zero(client):
    products = client.get("/api/products?max_price=990").json()["items"]
    zero_limit = client.get("/api/products?max_price=0").json()["items"]

    assert products
    assert all(item["cheapest"]["price"] <= 990 for item in products)
    assert any(item["cheapest"]["price"] == 990 for item in products)
    assert zero_limit == []

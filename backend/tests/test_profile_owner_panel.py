import pytest
from app.database import get_db


@pytest.mark.parametrize("owner", [True, False])
def test_profile_owner_panel_is_assigned_by_server(client, test_user, monkeypatch, owner):
    with get_db() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE email=?", (test_user["email"],)).fetchone()["id"]
    monkeypatch.setenv("PROFILE_OWNER_ID", user_id if owner else "another-user")
    created = client.post("/api/profile", json={
        "skin_types": ["sensitive"], "concerns": [], "budget_month": 5000,
    })
    assert created.status_code == 200
    profile_id = created.json()["profile_id"]
    result = client.get(f"/api/profile/{profile_id}").json()
    assert result["is_owner"] is owner
    assert ("stats" in result) is owner
    assert ("account_email" in result) is owner
    if owner:
        assert result["account_email"] == test_user["email"]
        assert set(result["stats"]) == {"favorites", "plan_items", "done_steps"}


def test_profile_owner_panel_is_disabled_without_configuration(client, test_user, monkeypatch):
    monkeypatch.delenv("PROFILE_OWNER_ID", raising=False)
    response = client.post("/api/profile", json={
        "skin_types": ["normal"], "concerns": [], "budget_month": 5000,
    })
    profile = client.get("/api/profile/" + response.json()["profile_id"]).json()
    assert profile["is_owner"] is False
    assert "stats" not in profile
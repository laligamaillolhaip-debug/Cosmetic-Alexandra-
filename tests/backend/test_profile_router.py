import pytest
from unittest.mock import patch

@patch("app.routers.profile.build_plan")
def test_create_profile(mock_build_plan, client, test_user):
    """Тест создания профиля (с моком build_plan)"""
    mock_build_plan.return_value = {
        "plan": {"morning": [], "evening": []},
        "spent": 0
    }
    
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    payload = {
        "skin_types": ["dry"],
        "concerns": ["acne"],
        "budget_month": 5000
    }
    response = client.post("/api/profile", json=payload)
    assert response.status_code == 200
    profile_id = response.json()["profile_id"]
    
    # Получаем профиль
    response = client.get(f"/api/profile/{profile_id}")
    assert response.status_code == 200
    assert response.json()["skin_types"] == ["dry"]

@patch("app.routers.profile.build_plan")
@patch("app.routers.profile.ai.skin_analysis")
def test_get_analysis(mock_skin_analysis, mock_build_plan, client, test_user):
    """Тест получения анализа кожи"""
    mock_build_plan.return_value = {"plan": {"morning": [], "evening": []}, "spent": 0}
    mock_skin_analysis.return_value = "У вас отличная кожа!"
    
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    # Создаем профиль
    profile_id = client.post("/api/profile", json={"skin_types": ["dry"], "concerns": [], "budget_month": 5000}).json()["profile_id"]
    
    # Запрашиваем анализ
    response = client.post(f"/api/profile/{profile_id}/analysis")
    assert response.status_code == 200
    assert response.json()["analysis"] == "У вас отличная кожа!"
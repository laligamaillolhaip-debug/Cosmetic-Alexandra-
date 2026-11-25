import uuid
from datetime import date
from app.database import get_db

def create_test_profile_and_product(user_email):
    """Вспомогательная функция для наполнения базы тестовыми данными."""
    with get_db() as conn:
        # Получаем user_id
        user = conn.execute("SELECT id FROM users WHERE email=?", (user_email,)).fetchone()
        if not user:
            return None, None
        
        profile_id = str(uuid.uuid4())
        product_id = str(uuid.uuid4())
        
        # Создаем профиль
        conn.execute(
            "INSERT INTO profiles (id, user_id, skin_types, concerns, budget_month, created_at) VALUES (?,?,?,?,?,?)",
            (profile_id, user["id"], '["dry"]', '["acne"]', 1000, date.today().isoformat())
        )
        
        # Создаем продукт
        conn.execute(
            "INSERT INTO products (id, name, brand, category, time_of_day, skin_types, concerns, actives, description) VALUES (?,?,?,?,?,?,?,?,?)",
            (product_id, "Test Product", "Brand", "cleanser", "morning", '["dry"]', '["acne"]', '["salicylic"]', "Test desc")
        )
        
        # Добавляем продукт в план
        conn.execute(
            "INSERT INTO plan_items (profile_id, product_id, time_of_day, step_order, badge, reason) VALUES (?,?,?,?,?,?)",
            (profile_id, product_id, "morning", 1, "badge", "reason")
        )
        
        return profile_id, product_id

def test_get_calendar_unauthorized(client):
    """Доступ к календарю без авторизации."""
    response = client.get("/api/calendar/some-profile-id")
    assert response.status_code == 401

def test_get_calendar_success(client, test_user):
    """Успешное получение календаря для своего профиля."""
    # Логинимся
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    # Создаем данные
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    
    # Запрашиваем календарь
    response = client.get(f"/api/calendar/{profile_id}?for_date=2023-10-01")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2023-10-01"
    assert len(data["checklist"]["morning"]) == 1
    assert data["checklist"]["morning"][0]["product"]["name"] == "Test Product"
    assert data["checklist"]["morning"][0]["done"] is False

def test_get_calendar_other_user(client, test_user):
    """Попытка получить календарь чужого профиля."""
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    # Создаем профиль для другого пользователя (вручную через БД)
    with get_db() as conn:
        other_user_id = str(uuid.uuid4())
        conn.execute("INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
                     (other_user_id, "other@example.com", "hash", date.today().isoformat()))
        
        other_profile_id = str(uuid.uuid4())
        conn.execute("INSERT INTO profiles (id, user_id, skin_types, concerns, budget_month, created_at) VALUES (?,?,?,?,?,?)",
                     (other_profile_id, other_user_id, '["dry"]', '["acne"]', 1000, date.today().isoformat()))
    
    # Пытаемся получить доступ
    response = client.get(f"/api/calendar/{other_profile_id}")
    assert response.status_code == 403
    assert "Это профиль другого пользователя" in response.json()["detail"]

def test_toggle_item(client, test_user):
    """Тест переключения статуса выполнения."""
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    
    # Переключаем на "Выполнено"
    payload = {
        "date": "2023-10-01",
        "time_of_day": "morning",
        "product_id": product_id,
        "done": True
    }
    response = client.post(f"/api/calendar/{profile_id}/toggle", json=payload)
    assert response.status_code == 200
    
    # Проверяем, что в календаре теперь done=True
    response = client.get(f"/api/calendar/{profile_id}?for_date=2023-10-01")
    assert response.json()["checklist"]["morning"][0]["done"] is True
    
    # Переключаем обратно на "Не выполнено"
    payload["done"] = False
    client.post(f"/api/calendar/{profile_id}/toggle", json=payload)
    
    response = client.get(f"/api/calendar/{profile_id}?for_date=2023-10-01")
    assert response.json()["checklist"]["morning"][0]["done"] is False
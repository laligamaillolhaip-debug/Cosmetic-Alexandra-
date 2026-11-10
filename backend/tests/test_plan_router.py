import pytest
from datetime import date
from app.database import get_db

def test_get_plan(client, test_user):
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    # Создаем профиль и продукт через функцию из calendar (она импортируется)
    from tests.test_calendar_router import create_test_profile_and_product
    profile_id, _ = create_test_profile_and_product(test_user["email"])
    
    response = client.get(f"/api/plan/{profile_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["id"] == profile_id
    assert len(data["plan"]["morning"]) > 0

def test_add_and_remove_item(client, test_user):
    from tests.test_calendar_router import create_test_profile_and_product
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    
    # Добавляем товар в вечернюю рутину
    payload = {"product_id": product_id, "time_of_day": "evening"}
    response = client.post(f"/api/plan/{profile_id}/items", json=payload)
    assert response.status_code == 200
    item_id = response.json()["item_id"]
    
    # Проверяем, что он появился в плане
    plan = client.get(f"/api/plan/{profile_id}").json()
    assert len(plan["plan"]["evening"]) == 1
    
    # Удаляем его
    response = client.delete(f"/api/plan/{profile_id}/items/{item_id}")
    assert response.status_code == 200
    
    # Проверяем, что он удалился
    plan = client.get(f"/api/plan/{profile_id}").json()
    assert len(plan["plan"]["evening"]) == 0

def test_reorder(client, test_user):
    from tests.test_calendar_router import create_test_profile_and_product
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    
    # Добавляем второй товар для теста
    with get_db() as conn:
        conn.execute("INSERT INTO products (id, name, brand, category, time_of_day, skin_types, concerns, actives, description) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("prod2", "Test2", "Brand", "serum", "morning", '[]', '[]', '[]', 'desc'))
    
    client.post(f"/api/plan/{profile_id}/items", json={"product_id": "prod2", "time_of_day": "morning"})
    
    # Получаем ID элементов
    plan = client.get(f"/api/plan/{profile_id}").json()
    item_ids = [item["item_id"] for item in plan["plan"]["morning"]]
    
    # Меняем порядок (реверс)
    payload = {"time_of_day": "morning", "item_ids": item_ids[::-1]}
    response = client.post(f"/api/plan/{profile_id}/reorder", json=payload)
    assert response.status_code == 200
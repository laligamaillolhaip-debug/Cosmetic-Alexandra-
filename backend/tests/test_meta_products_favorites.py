import pytest
import uuid
from datetime import date
from app.database import get_db
from tests.test_calendar_router import create_test_profile_and_product

def test_get_meta_options(client):
    response = client.get("/api/meta/options")
    assert response.status_code == 200
    data = response.json()
    assert len(data["skin_types"]) == 5
    assert len(data["concerns"]) == 6
    assert len(data["budget_presets"]) == 4

def test_get_meta_ai_status(client):
    response = client.get("/api/meta/ai-status")
    assert response.status_code == 200
    assert "ok" in response.json()

def test_list_products(client):
    product_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (id, name, brand, category, time_of_day, skin_types, concerns, actives, description) VALUES (?,?,?,?,?,?,?,?,?)",
            (product_id, "Test Product", "Brand", "serum", "morning", '["dry"]', '["acne"]', '["retinol"]', "Desc")
        )
        conn.execute(
            "INSERT INTO shop_prices (product_id, shop_name, price, updated_at) VALUES (?,?,?,?)",
            (product_id, "Shop1", 1000, date.today().isoformat())
        )

    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    assert "cheapest" in data["items"][0]

def test_list_products_filter_category(client):
    response = client.get("/api/products?category=serum")
    assert response.status_code == 200
    for p in response.json()["items"]:
        assert p["category"] == "serum"

def test_get_product_success(client):
    product_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (id, name, brand, category, time_of_day, skin_types, concerns, actives, description) VALUES (?,?,?,?,?,?,?,?,?)",
            (product_id, "Test Product 2", "Brand", "serum", "morning", '["dry"]', '["acne"]', '["retinol"]', "Desc")
        )
        conn.execute(
            "INSERT INTO shop_prices (product_id, shop_name, price, updated_at) VALUES (?,?,?,?)",
            (product_id, "Shop1", 1000, date.today().isoformat())
        )

    response = client.get(f"/api/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["product"]["id"] == product_id

def test_get_product_not_found(client):
    response = client.get("/api/products/non-existent-id")
    assert response.status_code == 404

def test_favorites_flow(client, test_user):
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, product_id = create_test_profile_and_product(test_user["email"])
    
    response = client.post(f"/api/favorites/{profile_id}", json={"product_id": product_id})
    assert response.status_code == 200
    
    response = client.get(f"/api/favorites/{profile_id}")
    assert len(response.json()["items"]) == 1
    
    response = client.delete(f"/api/favorites/{profile_id}/{product_id}")
    assert response.status_code == 200
    
    response = client.get(f"/api/favorites/{profile_id}")
    assert len(response.json()["items"]) == 0
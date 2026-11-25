from fastapi.testclient import TestClient

from app.main import app


def test_account_can_login_from_an_independent_device(client):
    credentials = {"email": "devices@example.com", "password": "secret123"}
    assert client.post("/api/auth/register", json=credentials).status_code == 200
    with TestClient(app) as second_device:
        assert second_device.get("/api/auth/me").status_code == 401
        response = second_device.post("/api/auth/login", json=credentials)
        assert response.status_code == 200
        assert second_device.cookies.get("yadro_session") != client.cookies.get("yadro_session")
        assert second_device.get("/api/auth/me").json()["email"] == credentials["email"]
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/auth/me").status_code == 401
        assert second_device.get("/api/auth/me").status_code == 200


def test_login_with_corrupted_password_hash_returns_401(client, db):
    db.execute("INSERT INTO users (id,email,password_hash,created_at) VALUES (?,?,?,?)",
               ("broken", "broken@example.com", "pbkdf2_sha256$abc$zz$yy", "2026-11-18"))
    db.commit()
    response = client.post("/api/auth/login", json={"email": "broken@example.com", "password": "secret123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверная почта или пароль"


def test_auth_routes_and_frontend_are_served_together(client):
    assert client.get("/login.html").status_code == 200
    assert client.get("/js/api.js").status_code == 200
    response = client.post("/api/auth/register", json={"email": "routes@example.com", "password": "secret123"})
    assert response.status_code == 200
    # An incorrect API path falls through to StaticFiles and produces the reported 405.
    assert client.post("/frontend/api/auth/register", json={}).status_code == 405


def test_email_case_does_not_depend_on_device(client):
    assert client.post("/api/auth/register", json={"email": "Mixed@example.com", "password": "secret123"}).status_code == 200
    with TestClient(app) as second_device:
        assert second_device.post("/api/auth/login", json={"email": "mixed@EXAMPLE.COM", "password": "secret123"}).status_code == 200

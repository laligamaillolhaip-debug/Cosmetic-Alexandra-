import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from app.main import app
from app import database
import uuid

def test_register_success(client):
    """Успешная регистрация: должен вернуться email, profile_id=None и установиться кука."""
    response = client.post("/api/auth/register", json={"email": "new@example.com", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["profile_id"] is None
    
    # Проверяем, что кука установилась
    assert "yadro_session" in response.cookies

def test_register_duplicate_email(client):
    """Попытка зарегистрироваться с уже существующим email."""
    email = "dup@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    
    # Вторая попытка
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 409
    assert "уже зарегистрирована" in response.json()["detail"]

def test_register_invalid_email(client):
    """Регистрация с некорректным email."""
    response = client.post("/api/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert response.status_code == 400
    assert "не адрес почты" in response.json()["detail"]

def test_register_short_password(client):
    """Регистрация со слишком коротким паролем."""
    response = client.post("/api/auth/register", json={"email": "short@example.com", "password": "123"})
    assert response.status_code == 400
    assert "не короче 6 символов" in response.json()["detail"]

def test_login_success(client, test_user):
    """Успешный вход по правильным данным."""
    response = client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    assert response.status_code == 200
    assert "yadro_session" in response.cookies
    assert response.json()["email"] == test_user["email"]

def test_login_wrong_password(client, test_user):
    """Вход с неверным паролем."""
    response = client.post("/api/auth/login", json={"email": test_user["email"], "password": "wrongpass"})
    assert response.status_code == 401
    assert "Неверная почта или пароль" in response.json()["detail"]

def test_login_no_user(client):
    """Вход с несуществующим email."""
    response = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert response.status_code == 401
    assert "Неверная почта или пароль" in response.json()["detail"]

def test_logout(client, test_user):
    """Выход из системы: кука должна удалиться."""
    # Сначала логинимся
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    
    # Выходим
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    
    # Проверяем, что куки больше нет (или она пустая)
    # В TestClient куки хранятся в client.cookies
    assert "yadro_session" not in client.cookies

def test_me_unauthorized(client):
    """Доступ к /me без авторизации."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Нужно войти в аккаунт" in response.json()["detail"]

def test_me_authorized(client, test_user):
    """Доступ к /me с авторизацией."""
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user["email"]
    assert data["profile_id"] is None
    assert data["budget_month"] is None
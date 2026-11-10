import sys
import os
import pytest
from fastapi.testclient import TestClient
import sqlite3
from pathlib import Path

# Импортируем приложение и базу
from app.main import app
from app import database

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """
    Фикстура для подмены реальной базы данных на временную.
    Выполняется перед каждым тестом.
    """
    test_db_path = tmp_path / "test_app.db"
    # Подменяем путь к базе в модуле database
    monkeypatch.setattr(database, "DB_PATH", test_db_path)
    
    # Инициализируем базу (создаем таблицы)
    database.init_db()
    
    yield  # Здесь выполняется сам тест
    
    # После теста временная база удаляется автоматически благодаря tmp_path

@pytest.fixture
def client():
    """Фикстура для тестового клиента FastAPI."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def test_user(client):
    """
    Фикстура, которая регистрирует тестового пользователя 
    и возвращает его данные (email, password).
    """
    email = "test@example.com"
    password = "secret123"
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"email": email, "password": password}
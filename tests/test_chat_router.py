import pytest
from unittest.mock import patch
from app.services import ai
from tests.test_calendar_router import create_test_profile_and_product # Импортируем нашу функцию

def test_get_history_empty(client, test_user):
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, _ = create_test_profile_and_product(test_user["email"])
    
    response = client.get(f"/api/chat/{profile_id}/history")
    assert response.status_code == 200
    assert response.json()["messages"] == []

@patch("app.services.ai.chat_reply")
def test_send_message_success(mock_chat_reply, client, test_user):
    """Тест успешной отправки сообщения с моком ИИ"""
    mock_chat_reply.return_value = "Это ответ от ИИ."
    
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, _ = create_test_profile_and_product(test_user["email"])
    
    response = client.post(f"/api/chat/{profile_id}", json={"message": "Привет, ИИ!"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Это ответ от ИИ."
    
    # Проверяем, что в истории теперь 2 сообщения (вопрос и ответ)
    history_response = client.get(f"/api/chat/{profile_id}/history")
    messages = history_response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Привет, ИИ!"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Это ответ от ИИ."

@patch("app.services.ai.chat_reply")
def test_send_message_ai_unavailable(mock_chat_reply, client, test_user):
    """Тест, если ИИ недоступен (кидает ошибку)"""
    mock_chat_reply.side_effect = ai.AIUnavailable("ИИ спит")
    
    client.post("/api/auth/login", json={"email": test_user["email"], "password": test_user["password"]})
    profile_id, _ = create_test_profile_and_product(test_user["email"])
    
    response = client.post(f"/api/chat/{profile_id}", json={"message": "Привет"})
    assert response.status_code == 503
    assert response.json()["detail"] == "ИИ спит"
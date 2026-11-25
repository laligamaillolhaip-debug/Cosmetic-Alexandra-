import pytest
from app.services.ai import _strip_reasoning, _profile_context

def test_strip_reasoning():
    text_with_reasoning = "<thought>Думаю...</thought>Ответ для пользователя"
    assert _strip_reasoning(text_with_reasoning) == "<thought>Думаю...</thought>Ответ для пользователя"
    
    text_clean = "Просто ответ"
    assert _strip_reasoning(text_clean) == "Просто ответ"

def test_profile_context():
    profile = {
        "skin_types": ["dry", "sensitive"],
        "concerns": ["acne"],
        "budget_month": 5000
    }
    context = _profile_context(profile)
    assert "Тип кожи: сухая, чувствительная" in context
    assert "Проблемы: акне" in context
    assert "Бюджет на уход: 5000" in context
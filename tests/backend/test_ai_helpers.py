import pytest
from app.services.ai import _strip_reasoning, _profile_context


@pytest.mark.parametrize(("text", "expected"), [
    ("<think>Думаю...</think>Ответ", "Ответ"),
    ("<THINK>\nДумаю...\n</THINK>\nОтвет", "Ответ"),
    ("<reasoning>Шаг 1\nШаг 2</reasoning>Ответ", "Ответ"),
    ("<think>Внутреннее</think><reasoning>Ещё</reasoning>Ответ", "Ответ"),
    ("<thought>Оставить</thought>Ответ", "<thought>Оставить</thought>Ответ"),
    ("Просто ответ", "Просто ответ"),
])
def test_strip_reasoning(text, expected):
    assert _strip_reasoning(text) == expected

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
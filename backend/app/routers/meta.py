from fastapi import APIRouter

from ..services import ai

router = APIRouter(prefix="/api/meta", tags=["meta"])

SKIN_TYPES = [
    {"id": "dry", "label": "Сухая", "hint": "Стянутость, шелушение"},
    {"id": "oily", "label": "Жирная", "hint": "Блеск, расширенные поры"},
    {"id": "combination", "label": "Комбинированная", "hint": "Т-зона жирная, щёки сухие"},
    {"id": "sensitive", "label": "Чувствительная", "hint": "Покраснения, реакции"},
    {"id": "normal", "label": "Нормальная", "hint": "Без выраженных проблем"},
]

CONCERNS = [
    {"id": "acne", "label": "Акне и воспаления"},
    {"id": "pores", "label": "Расширенные поры"},
    {"id": "dehydration", "label": "Обезвоженность"},
    {"id": "sensitivity", "label": "Раздражения после бритья"},
    {"id": "aging", "label": "Первые признаки старения"},
    {"id": "dullness", "label": "Тусклый цвет лица"},
]

BUDGET_PRESETS = [
    {"label": "До 3 000 ₽", "min": 300, "max": 3000},
    {"label": "3 000–7 000 ₽", "min": 3000, "max": 7000},
    {"label": "7 000–15 000 ₽", "min": 7000, "max": 15000},
    {"label": "Без лимита", "min": 15000, "max": 50000},
]


@router.get("/options")
def get_options():
    return {"skin_types": SKIN_TYPES, "concerns": CONCERNS, "budget_presets": BUDGET_PRESETS}


@router.get("/ai-status")
def ai_status():
    """Подключена ли модель — интерфейс показывает это, чтобы не гадать."""
    return ai.status()

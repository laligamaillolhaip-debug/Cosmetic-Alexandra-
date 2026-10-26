import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import ProfileIn
from ..services import ai, auth
from ..services.matching import build_plan
from .products import load_products_with_prices

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("")
def create_profile(payload: ProfileIn, user: dict = Depends(auth.current_user)):
    """
    Профиль всегда принадлежит аккаунту. Если человек проходит опрос повторно,
    второй профиль не заводим — обновляем существующий.
    """
    now = datetime.now(timezone.utc).isoformat()
    skin_types = json.dumps(payload.skin_types, ensure_ascii=False)
    concerns = json.dumps(payload.concerns, ensure_ascii=False)

    with get_db() as conn:
        profile_id = auth.profile_id_of(conn, user["id"])
        if profile_id:
            conn.execute(
                """UPDATE profiles SET skin_types=?, concerns=?, budget_month=?, analysis=NULL
                   WHERE id=?""",
                (skin_types, concerns, payload.budget_month, profile_id),
            )
        else:
            profile_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO profiles (id, user_id, skin_types, concerns, budget_month, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (profile_id, user["id"], skin_types, concerns, payload.budget_month, now),
            )
        products, prices = load_products_with_prices(conn)
        result = build_plan(payload.model_dump(), products, prices)
        save_plan(conn, profile_id, result["plan"])
    return {"profile_id": profile_id}


@router.get("/{profile_id}")
def get_profile(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Профиль не найден")
        profile = row_to_dict(row)
        profile["stats"] = {
            "favorites": conn.execute(
                "SELECT COUNT(*) c FROM favorites WHERE profile_id=?", (profile_id,)
            ).fetchone()["c"],
            "plan_items": conn.execute(
                "SELECT COUNT(DISTINCT product_id) c FROM plan_items WHERE profile_id=?", (profile_id,)
            ).fetchone()["c"],
            "done_steps": conn.execute(
                "SELECT COUNT(*) c FROM routine_log WHERE profile_id=? AND done=1", (profile_id,)
            ).fetchone()["c"],
        }
    return profile


@router.put("/{profile_id}")
def update_profile(payload: ProfileIn, profile_id: str = Depends(auth.require_profile_access)):
    """
    Перепрохождение опросника: обновляем ответы и пересобираем план.
    Избранное, отметки в календаре и переписка с ИИ сохраняются —
    теряется только устаревший разбор кожи, он пересчитается заново.
    """
    with get_db() as conn:
        row = conn.execute("SELECT id FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Профиль не найден")

        conn.execute(
            """UPDATE profiles SET skin_types=?, concerns=?, budget_month=?, analysis=NULL
               WHERE id=?""",
            (
                json.dumps(payload.skin_types, ensure_ascii=False),
                json.dumps(payload.concerns, ensure_ascii=False),
                payload.budget_month,
                profile_id,
            ),
        )
        products, prices = load_products_with_prices(conn)
        result = build_plan(payload.model_dump(), products, prices)
        save_plan(conn, profile_id, result["plan"])

    return {"profile_id": profile_id, "spent": result["spent"]}


@router.post("/{profile_id}/analysis")
def get_analysis(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Профиль не найден")
        profile = row_to_dict(row)
        if profile.get("analysis"):
            return {"analysis": profile["analysis"]}
        try:
            text = ai.skin_analysis(profile)
        except ai.AIUnavailable as e:
            return {"analysis": None, "error": str(e)}
        conn.execute("UPDATE profiles SET analysis=? WHERE id=?", (text, profile_id))
        return {"analysis": text}


def save_plan(conn, profile_id: str, plan: dict):
    conn.execute("DELETE FROM plan_items WHERE profile_id=?", (profile_id,))
    for time_of_day, items in plan.items():
        for order, item in enumerate(items):
            conn.execute(
                """INSERT INTO plan_items (profile_id, product_id, time_of_day, step_order, badge, reason)
                   VALUES (?,?,?,?,?,?)""",
                (profile_id, item["product"]["id"], time_of_day, order, item["badge"], item["reason"]),
            )

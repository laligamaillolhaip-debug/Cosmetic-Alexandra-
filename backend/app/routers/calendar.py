from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import ToggleIn
from ..services import auth

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/{profile_id}")
def get_day(for_date: str = "", profile_id: str = Depends(auth.require_profile_access)):
    day = for_date or date.today().isoformat()
    with get_db() as conn:
        profile_row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not profile_row:
            raise HTTPException(404, "Профиль не найден")

        plan_items = conn.execute(
            "SELECT DISTINCT product_id, time_of_day FROM plan_items WHERE profile_id=?", (profile_id,)
        ).fetchall()
        done_rows = {
            (r["product_id"], r["time_of_day"]): bool(r["done"])
            for r in conn.execute(
                "SELECT product_id, time_of_day, done FROM routine_log WHERE profile_id=? AND date=?",
                (profile_id, day),
            ).fetchall()
        }

        result = {"morning": [], "evening": []}
        for item in plan_items:
            product = row_to_dict(conn.execute(
                "SELECT * FROM products WHERE id=?", (item["product_id"],)
            ).fetchone())
            done = done_rows.get((item["product_id"], item["time_of_day"]), False)
            result[item["time_of_day"]].append({"product": product, "done": done})

    return {"date": day, "checklist": result}


@router.post("/{profile_id}/toggle")
def toggle(payload: ToggleIn, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO routine_log (profile_id, date, time_of_day, product_id, done)
               VALUES (?,?,?,?,?)
               ON CONFLICT(profile_id, date, time_of_day, product_id)
               DO UPDATE SET done=excluded.done""",
            (profile_id, payload.date, payload.time_of_day, payload.product_id, int(payload.done)),
        )
    return {"ok": True}

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import PlanItemIn, ReorderIn
from ..services import auth
from ..services.matching import CATEGORY_LABELS

router = APIRouter(prefix="/api/plan", tags=["plan"])


@router.get("/{profile_id}")
def get_plan(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        profile_row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not profile_row:
            raise HTTPException(404, "Профиль не найден")
        profile = row_to_dict(profile_row)

        items = conn.execute(
            "SELECT * FROM plan_items WHERE profile_id=? ORDER BY time_of_day, step_order", (profile_id,)
        ).fetchall()

        plan = {"morning": [], "evening": []}
        total_spent = 0
        counted_products = set()

        for item in items:
            product = row_to_dict(conn.execute(
                "SELECT * FROM products WHERE id=?", (item["product_id"],)
            ).fetchone())
            cheapest = conn.execute(
                "SELECT * FROM shop_prices WHERE product_id=? ORDER BY price ASC LIMIT 1", (item["product_id"],)
            ).fetchone()
            price = dict(cheapest) if cheapest else None

            plan[item["time_of_day"]].append({
                "item_id": item["id"],
                "product": product,
                "price": price,
                "badge": item["badge"],
                "reason": item["reason"],
                "category_label": CATEGORY_LABELS.get(product["category"], product["category"]),
            })
            if item["product_id"] not in counted_products and price:
                total_spent += price["price"]
                counted_products.add(item["product_id"])

    return {"profile": profile, "plan": plan, "spent": total_spent, "budget": profile["budget_month"]}


@router.post("/{profile_id}/items")
def add_item(payload: PlanItemIn, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        exists = conn.execute(
            "SELECT id FROM plan_items WHERE profile_id=? AND product_id=? AND time_of_day=?",
            (profile_id, payload.product_id, payload.time_of_day),
        ).fetchone()
        if exists:
            return {"ok": True, "item_id": exists["id"], "already": True}

        product = conn.execute("SELECT id FROM products WHERE id=?", (payload.product_id,)).fetchone()
        if not product:
            raise HTTPException(404, "Товар не найден")

        max_order = conn.execute(
            "SELECT COALESCE(MAX(step_order), -1) m FROM plan_items WHERE profile_id=? AND time_of_day=?",
            (profile_id, payload.time_of_day),
        ).fetchone()["m"]

        cur = conn.execute(
            """INSERT INTO plan_items (profile_id, product_id, time_of_day, step_order, badge, reason)
               VALUES (?,?,?,?,?,?)""",
            (profile_id, payload.product_id, payload.time_of_day, max_order + 1,
             "manual", "Добавлено вручную из избранного"),
        )
    return {"ok": True, "item_id": cur.lastrowid}


@router.delete("/{profile_id}/items/{item_id}")
def remove_item(item_id: int, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute("DELETE FROM plan_items WHERE profile_id=? AND id=?", (profile_id, item_id))
    return {"ok": True}


@router.post("/{profile_id}/reorder")
def reorder(payload: ReorderIn, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        for order, item_id in enumerate(payload.item_ids):
            conn.execute(
                "UPDATE plan_items SET step_order=? WHERE profile_id=? AND id=? AND time_of_day=?",
                (order, profile_id, item_id, payload.time_of_day),
            )
    return {"ok": True}

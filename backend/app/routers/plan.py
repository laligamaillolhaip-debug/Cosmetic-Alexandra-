import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import PlanItemIn, ReorderIn
from ..services import auth, ai, ai_planner
from .products import load_products_with_prices
from .profile import save_plan
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

        conn.execute("UPDATE profiles SET plan_source='edited', plan_summary=NULL WHERE id=?", (profile_id,))
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
        conn.execute("UPDATE profiles SET plan_source='edited', plan_summary=NULL WHERE id=?", (profile_id,))
        conn.execute("DELETE FROM plan_items WHERE profile_id=? AND id=?", (profile_id, item_id))
    return {"ok": True}


@router.post("/{profile_id}/reorder")
def reorder(payload: ReorderIn, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute("UPDATE profiles SET plan_source='edited', plan_summary=NULL WHERE id=?", (profile_id,))
        for order, item_id in enumerate(payload.item_ids):
            conn.execute(
                "UPDATE plan_items SET step_order=? WHERE profile_id=? AND id=? AND time_of_day=?",
                (order, profile_id, item_id, payload.time_of_day),
            )
    return {"ok": True}


@router.post("/{profile_id}/ai-draft")
def create_ai_draft(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        profile = row_to_dict(conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())
        products, prices = load_products_with_prices(conn)
        stamp = ai_planner.fingerprint(conn, profile, products, prices)
    try:
        result = ai_planner.generate(profile, products, prices)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ai_planner.InvalidPlan as exc:
        raise HTTPException(422, str(exc)) from exc
    draft_id = str(uuid.uuid4())
    model = ai.ANTHROPIC_MODEL if ai.PROVIDER == "anthropic" else ai.LOCAL_MODEL
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        latest = row_to_dict(conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())
        current_products, current_prices = load_products_with_prices(conn)
        if stamp != ai_planner.fingerprint(conn, latest, current_products, current_prices):
            raise HTTPException(409, "Профиль, каталог или план изменились во время подбора. Запусти подбор ещё раз.")
        conn.execute("DELETE FROM plan_drafts WHERE profile_id=?", (profile_id,))
        conn.execute("INSERT INTO plan_drafts (id,profile_id,selection_json,fingerprint,model,created_at) VALUES (?,?,?,?,?,?)",
                     (draft_id, profile_id, json.dumps(ai_planner.selection_from_result(result), ensure_ascii=False), stamp, model, now.isoformat()))
    return {**result, "draft_id": draft_id}


@router.post("/{profile_id}/ai-draft/{draft_id}/apply")
def apply_ai_draft(draft_id: str, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        draft = conn.execute("SELECT * FROM plan_drafts WHERE id=? AND profile_id=?", (draft_id, profile_id)).fetchone()
        if not draft:
            raise HTTPException(404, "Предложение не найдено. Выполни новый подбор.")
        if datetime.now(timezone.utc) - datetime.fromisoformat(draft["created_at"]) > timedelta(minutes=30):
            raise HTTPException(409, "Предложение устарело. Выполни новый подбор.")
        profile = row_to_dict(conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())
        products, prices = load_products_with_prices(conn)
        if draft["fingerprint"] != ai_planner.fingerprint(conn, profile, products, prices):
            raise HTTPException(409, "Профиль, каталог или текущий план изменились. Нужен новый подбор.")
        try:
            result = ai_planner.validate_selection(json.loads(draft["selection_json"]), profile, ai_planner.candidates(profile, products, prices))
        except ai_planner.InvalidPlan as exc:
            raise HTTPException(409, "Предложение больше не подходит: " + str(exc)) from exc
        save_plan(conn, profile_id, result["plan"], source="ai", summary=result["summary"], model=draft["model"])
        conn.execute("DELETE FROM plan_drafts WHERE profile_id=?", (profile_id,))
    return get_plan(profile_id)


@router.get("/{profile_id}/ai-draft")
def latest_ai_draft(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        draft = conn.execute("SELECT * FROM plan_drafts WHERE profile_id=? ORDER BY created_at DESC LIMIT 1", (profile_id,)).fetchone()
        if not draft or datetime.now(timezone.utc) - datetime.fromisoformat(draft["created_at"]) > timedelta(minutes=30):
            return {"draft": None}
        profile = row_to_dict(conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())
        products, prices = load_products_with_prices(conn)
        if draft["fingerprint"] != ai_planner.fingerprint(conn, profile, products, prices):
            return {"draft": None}
        try:
            result = ai_planner.validate_selection(json.loads(draft["selection_json"]), profile, ai_planner.candidates(profile, products, prices))
        except ai_planner.InvalidPlan:
            return {"draft": None}
        return {"draft": {**result, "draft_id": draft["id"]}}


@router.delete("/{profile_id}/ai-draft/{draft_id}")
def dismiss_ai_draft(draft_id: str, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute("DELETE FROM plan_drafts WHERE id=? AND profile_id=?", (draft_id, profile_id))
    return {"ok": True}

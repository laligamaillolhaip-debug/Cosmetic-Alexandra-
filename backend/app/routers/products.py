import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import AdviceIn
from ..services import ai, auth
from ..services.matching import CATEGORY_LABELS, cheapest_price

router = APIRouter(prefix="/api/products", tags=["products"])


def load_products_with_prices(conn: sqlite3.Connection):
    products = [row_to_dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    prices_by_product: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT * FROM shop_prices").fetchall():
        d = dict(r)
        prices_by_product.setdefault(d["product_id"], []).append(d)
    return products, prices_by_product


@router.get("")
def list_products(query: str = "", category: str = "", max_price: int | None = None):
    with get_db() as conn:
        products, prices = load_products_with_prices(conn)

    result = []
    for p in products:
        if category and p["category"] != category:
            continue
        if query and query.lower() not in p["name"].lower() and query.lower() not in p["brand"].lower():
            continue
        cheapest = cheapest_price(prices.get(p["id"], []))
        if not cheapest:
            continue
        if max_price and cheapest["price"] > max_price:
            continue
        result.append({
            "product": p,
            "cheapest": cheapest,
            "shop_count": len(prices.get(p["id"], [])),
            "category_label": CATEGORY_LABELS.get(p["category"], p["category"]),
        })
    result.sort(key=lambda x: x["cheapest"]["price"])
    return {"items": result, "categories": sorted(CATEGORY_LABELS.items())}


@router.get("/{product_id}")
def get_product(product_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Товар не найден")
        product = row_to_dict(row)
        prices = [dict(r) for r in conn.execute(
            "SELECT * FROM shop_prices WHERE product_id=? ORDER BY price ASC", (product_id,)
        ).fetchall()]
    return {"product": product, "prices": prices, "category_label": CATEGORY_LABELS.get(product["category"], product["category"])}


@router.post("/{product_id}/ai-advice")
def ai_advice(product_id: str, payload: AdviceIn,
              user: dict = Depends(auth.current_user)):
    with get_db() as conn:
        product_row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product_row:
            raise HTTPException(404, "Товар не найден")
        product = row_to_dict(product_row)

        profile_row = conn.execute(
            "SELECT * FROM profiles WHERE id=? AND user_id=?",
            (payload.profile_id, user["id"]),
        ).fetchone()
        if not profile_row:
            raise HTTPException(404, "Профиль не найден")
        profile = row_to_dict(profile_row)

        plan_product_ids = [r["product_id"] for r in conn.execute(
            "SELECT DISTINCT product_id FROM plan_items WHERE profile_id=?", (payload.profile_id,)
        ).fetchall()]
        plan_products = [row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM products WHERE id IN ({','.join('?' * len(plan_product_ids))})", plan_product_ids
        ).fetchall()] if plan_product_ids else []

    try:
        text = ai.product_advice(profile, product, plan_products)
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"advice": text}

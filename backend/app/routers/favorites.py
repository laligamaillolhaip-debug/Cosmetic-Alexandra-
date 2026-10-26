from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..database import get_db, row_to_dict
from ..schemas import FavoriteIn
from ..services import auth
from ..services.matching import CATEGORY_LABELS

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("/{profile_id}")
def list_favorites(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT product_id FROM favorites WHERE profile_id=? ORDER BY created_at DESC", (profile_id,)
        ).fetchall()
        items = []
        for row in rows:
            product_row = conn.execute("SELECT * FROM products WHERE id=?", (row["product_id"],)).fetchone()
            if not product_row:
                continue
            product = row_to_dict(product_row)
            cheapest = conn.execute(
                "SELECT * FROM shop_prices WHERE product_id=? ORDER BY price ASC LIMIT 1", (row["product_id"],)
            ).fetchone()
            items.append({
                "product": product,
                "price": dict(cheapest) if cheapest else None,
                "category_label": CATEGORY_LABELS.get(product["category"], product["category"]),
            })
    return {"items": items, "ids": [r["product_id"] for r in rows]}


@router.post("/{profile_id}")
def add_favorite(payload: FavoriteIn, profile_id: str = Depends(auth.require_profile_access)):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO favorites (profile_id, product_id, created_at) VALUES (?,?,?)
               ON CONFLICT(profile_id, product_id) DO NOTHING""",
            (profile_id, payload.product_id, now),
        )
    return {"ok": True}


@router.delete("/{profile_id}/{product_id}")
def remove_favorite(product_id: str, profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        conn.execute("DELETE FROM favorites WHERE profile_id=? AND product_id=?", (profile_id, product_id))
    return {"ok": True}

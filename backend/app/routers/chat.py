from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, row_to_dict
from ..schemas import ChatIn
from ..services import ai, auth

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/{profile_id}/history")
def history(profile_id: str = Depends(auth.require_profile_access)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE profile_id=? ORDER BY id", (profile_id,)
        ).fetchall()
    return {"messages": [dict(r) for r in rows]}


@router.post("/{profile_id}")
def send_message(payload: ChatIn, profile_id: str = Depends(auth.require_profile_access)):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        profile_row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not profile_row:
            raise HTTPException(404, "Профиль не найден")
        profile = row_to_dict(profile_row)

        history_rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE profile_id=? ORDER BY id", (profile_id,)
        ).fetchall()
        history = [dict(r) for r in history_rows]

        plan_product_ids = [r["product_id"] for r in conn.execute(
            "SELECT DISTINCT product_id FROM plan_items WHERE profile_id=?", (profile_id,)
        ).fetchall()]
        plan_products = [row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM products WHERE id IN ({','.join('?' * len(plan_product_ids))})", plan_product_ids
        ).fetchall()] if plan_product_ids else []

        conn.execute(
            "INSERT INTO chat_messages (profile_id, role, content, created_at) VALUES (?,?,?,?)",
            (profile_id, "user", payload.message, now),
        )

        try:
            reply = ai.chat_reply(profile, plan_products, history, payload.message)
        except ai.AIUnavailable as e:
            raise HTTPException(503, str(e)) from e

        conn.execute(
            "INSERT INTO chat_messages (profile_id, role, content, created_at) VALUES (?,?,?,?)",
            (profile_id, "assistant", reply, now),
        )

    return {"reply": reply}

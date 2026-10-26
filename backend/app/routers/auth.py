import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..database import get_db
from ..schemas import CredentialsIn
from ..services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,      # недоступна из JavaScript
        samesite="lax",     # не уходит на чужие сайты
        path="/",
    )


@router.post("/register")
def register(payload: CredentialsIn, response: Response):
    email = payload.email.strip()
    auth.validate_credentials(email, payload.password)

    with get_db() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if exists:
            raise HTTPException(409, "Такая почта уже зарегистрирована")

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
            (user_id, email, auth.hash_password(payload.password),
             datetime.now(timezone.utc).isoformat()),
        )
        token = auth.create_session(conn, user_id)

    _set_session_cookie(response, token)
    return {"email": email, "profile_id": None}


@router.post("/login")
def login(payload: CredentialsIn, response: Response):
    email = payload.email.strip()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        # одинаковый ответ на «нет такой почты» и «неверный пароль»:
        # иначе по разнице сообщений можно перебирать существующие аккаунты
        if not row or not auth.verify_password(payload.password, row["password_hash"]):
            raise HTTPException(401, "Неверная почта или пароль")
        token = auth.create_session(conn, row["id"])
        profile_id = auth.profile_id_of(conn, row["id"])

    _set_session_cookie(response, token)
    return {"email": row["email"], "profile_id": profile_id}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        with get_db() as conn:
            auth.drop_session(conn, token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    """Кто вошёл и есть ли у него собранный профиль."""
    with get_db() as conn:
        profile_id = auth.profile_id_of(conn, user["id"])
        budget = None
        if profile_id:
            row = conn.execute(
                "SELECT budget_month FROM profiles WHERE id=?", (profile_id,)
            ).fetchone()
            budget = row["budget_month"] if row else None
    return {"email": user["email"], "profile_id": profile_id, "budget_month": budget}

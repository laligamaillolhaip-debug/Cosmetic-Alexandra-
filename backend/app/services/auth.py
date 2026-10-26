"""
Регистрация, вход и сессии.

Пароли не хранятся: в базе лежит только хэш PBKDF2-HMAC-SHA256 с индивидуальной
солью. Реализовано на стандартной библиотеке — внешних пакетов вроде bcrypt
не требуется.

Сессия — случайный токен в таблице sessions, который отдаётся браузеру в
httpOnly-куке: JavaScript до него не доберётся, поэтому украсть его со страницы
нельзя.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request

from ..database import get_db

COOKIE_NAME = "yadro_session"
SESSION_DAYS = 30
PBKDF2_ROUNDS = 200_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Zа-яА-Я]{2,}$")


# ──────────────────────────── пароли ────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(rounds))
    # сравнение с защитой от подбора по времени ответа
    return hmac.compare_digest(digest.hex(), digest_hex)


def validate_credentials(email: str, password: str) -> None:
    if not EMAIL_RE.match(email.strip()):
        raise HTTPException(400, "Похоже, это не адрес почты")
    if len(password) < 6:
        raise HTTPException(400, "Пароль должен быть не короче 6 символов")


# ──────────────────────────── сессии ────────────────────────────

def create_session(conn, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat()),
    )
    return token


def drop_session(conn, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def user_by_token(conn, token: str) -> dict | None:
    row = conn.execute(
        """SELECT u.id, u.email, s.expires_at
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ?""",
        (token,),
    ).fetchone()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return {"id": row["id"], "email": row["email"]}


# ──────────────────────── зависимости FastAPI ────────────────────────

def current_user(request: Request) -> dict:
    """Пускает дальше только вошедшего пользователя."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Нужно войти в аккаунт")
    with get_db() as conn:
        user = user_by_token(conn, token)
    if not user:
        raise HTTPException(401, "Сессия истекла, войдите заново")
    return user


def optional_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    with get_db() as conn:
        return user_by_token(conn, token)


def require_profile_access(profile_id: str, user: dict = Depends(current_user)) -> str:
    """
    Профиль принадлежит аккаунту: чужой чужому не отдаём.
    Без этой проверки знание чужого id открывало бы доступ к его плану.
    """
    with get_db() as conn:
        row = conn.execute("SELECT user_id FROM profiles WHERE id=?", (profile_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Профиль не найден")
    if row["user_id"] != user["id"]:
        raise HTTPException(403, "Это профиль другого пользователя")
    return profile_id


def profile_id_of(conn, user_id: str) -> str | None:
    row = conn.execute("SELECT id FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    return row["id"] if row else None

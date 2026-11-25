import pytest
from fastapi import HTTPException
from app.services.auth import (
    hash_password,
    verify_password,
    validate_credentials,
    create_session,
    user_by_token,
    drop_session
)

@pytest.mark.parametrize("email, password, ok", [
    ("a@b.co", "123456", True),
    ("a@b.c", "123456", False),
    ("a@b", "123456", False),
    ("a b@c.de", "123456", False),
    ("a@b.co", "12345", False),
    (" a@b.co ", "123456", True),
    ("ё@почта.рф", "123456", True),
    ("a@b..co", "123456", True),
    ("", "123456", False),
])
def test_validate_credentials(email, password, ok):
    if ok:
        validate_credentials(email, password)
    else:
        with pytest.raises(HTTPException) as err:
            validate_credentials(email, password)
        assert err.value.status_code == 400

@pytest.mark.parametrize("email", [
    "plain",
    "@example.com",
    "user@",
    "user@example",
    "user @example.com",
    "user@example.",
])
def test_validate_credentials_rejects_malformed_email(email):
    with pytest.raises(HTTPException) as err:
        validate_credentials(email, "123456")
    assert err.value.status_code == 400
    assert "не адрес почты" in err.value.detail


@pytest.mark.parametrize(("password", "is_valid"), [
    ("", False),
    ("a", False),
    ("12345", False),
    ("123456", True),
])
def test_validate_credentials_password_business_boundary(password, is_valid):
    if is_valid:
        validate_credentials("valid@example.com", password)
    else:
        with pytest.raises(HTTPException) as err:
            validate_credentials("valid@example.com", password)
        assert err.value.status_code == 400

def test_hash_and_verify_password():
    pwd = "supersecret"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2_sha256$200000$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_verify_password_invalid_format():
    assert verify_password("123456", "invalid_format") is False

@pytest.mark.parametrize("stored", [
    "pbkdf2_sha256$abc$zz$yy",
    "pbkdf2_sha256$0$aa$" + "00" * 32,
    "pbkdf2_sha256$-1$aa$" + "00" * 32,
    "pbkdf2_sha256$200000$$" + "00" * 32,
    "pbkdf2_sha256$200000$aa$yy",
    "pbkdf2_sha256$200000$aa$00",
    "pbkdf2_sha256$999999999999999999999999$aa$" + "00" * 32,
    None,
])
def test_verify_password_broken_hash(stored):
    assert verify_password("123456", stored) is False

def test_create_and_drop_session(db):
    from datetime import datetime, timezone
    
    db.execute(
        "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
        ("user123", "test_session@test.ru", "hash", datetime.now(timezone.utc).isoformat())
    )
    
    token = create_session(db, "user123")
    assert token is not None
    
    user = user_by_token(db, token)
    assert user["id"] == "user123"
    
    drop_session(db, token)
    assert user_by_token(db, token) is None

def test_user_by_token_expired(db):
    from datetime import datetime, timezone, timedelta
    
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db.execute(
        "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
        ("u1", "test@test.ru", "hash", datetime.now(timezone.utc).isoformat())
    )
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        ("expired_token", "u1", datetime.now(timezone.utc).isoformat(), past_time)
    )
    
    assert user_by_token(db, "expired_token") is None
    
    row = db.execute("SELECT * FROM sessions WHERE token=?", ("expired_token",)).fetchone()
    assert row is None
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    skin_types TEXT NOT NULL,
    concerns TEXT NOT NULL,
    budget_month INTEGER NOT NULL,
    analysis TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    volume_ml INTEGER,
    time_of_day TEXT NOT NULL,
    skin_types TEXT NOT NULL,
    concerns TEXT NOT NULL,
    actives TEXT NOT NULL,
    description TEXT NOT NULL,
    popularity INTEGER NOT NULL DEFAULT 50,
    icon TEXT NOT NULL DEFAULT 'drop'
);

CREATE TABLE IF NOT EXISTS shop_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES products(id),
    shop_name TEXT NOT NULL,
    price INTEGER NOT NULL,
    url TEXT,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed'
);

CREATE TABLE IF NOT EXISTS plan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    time_of_day TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    badge TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(profile_id, product_id)
);

CREATE TABLE IF NOT EXISTS routine_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    date TEXT NOT NULL,
    time_of_day TEXT NOT NULL,
    product_id TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    UNIQUE(profile_id, date, time_of_day, product_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        count = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
        if count == 0:
            from .seed_data import seed_all
            seed_all(conn)


def _migrate(conn):
    """Досоздаёт колонки, появившиеся позже, чтобы старая база не ломалась."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(profiles)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE profiles ADD COLUMN user_id TEXT REFERENCES users(id)")


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("concerns", "skin_types", "actives"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d

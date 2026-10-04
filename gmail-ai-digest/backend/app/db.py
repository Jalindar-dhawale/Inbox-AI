import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from .config import get_settings

def _connect() -> sqlite3.Connection:
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection

@contextmanager
def database():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()

def initialize_database() -> None:
    with database() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
          provider_user_id TEXT NOT NULL, email TEXT NOT NULL, name TEXT NOT NULL,
          avatar_url TEXT, created_at TEXT NOT NULL, UNIQUE(provider, provider_user_id));
        CREATE TABLE IF NOT EXISTS mailbox_connections (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          provider TEXT NOT NULL, encrypted_tokens TEXT NOT NULL, scopes TEXT,
          updated_at TEXT NOT NULL, UNIQUE(user_id, provider),
          FOREIGN KEY(user_id) REFERENCES users(id));
        """)

def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required for OAuth token storage")
    return Fernet(key.encode())

def upsert_user(provider: str, profile: dict, tokens: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    provider_id = str(profile["id"])
    with database() as connection:
        connection.execute("""INSERT INTO users(provider,provider_user_id,email,name,avatar_url,created_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(provider,provider_user_id) DO UPDATE SET
          email=excluded.email,name=excluded.name,avatar_url=excluded.avatar_url""",
          (provider, provider_id, profile["email"], profile["name"], profile.get("avatar"), now))
        user = connection.execute("SELECT id FROM users WHERE provider=? AND provider_user_id=?", (provider, provider_id)).fetchone()
        existing = connection.execute(
            "SELECT encrypted_tokens FROM mailbox_connections WHERE user_id=? AND provider=?",
            (user["id"], provider),
        ).fetchone()
        previous = json.loads(_fernet().decrypt(existing["encrypted_tokens"].encode()).decode()) if existing else {}
        merged_tokens = {**previous, **tokens, "obtained_at": now}
        encrypted = _fernet().encrypt(json.dumps(merged_tokens).encode()).decode()
        scopes = merged_tokens.get("scope", "")
        if isinstance(scopes, list): scopes = " ".join(scopes)
        connection.execute("""INSERT INTO mailbox_connections(user_id,provider,encrypted_tokens,scopes,updated_at)
          VALUES(?,?,?,?,?) ON CONFLICT(user_id,provider) DO UPDATE SET
          encrypted_tokens=excluded.encrypted_tokens,scopes=excluded.scopes,updated_at=excluded.updated_at""",
          (user["id"], provider, encrypted, scopes, now))
        return int(user["id"])

def save_tokens(user_id: int, provider: str, tokens: dict) -> None:
    encrypted = _fernet().encrypt(json.dumps(tokens).encode()).decode()
    with database() as connection:
        connection.execute(
            "UPDATE mailbox_connections SET encrypted_tokens=?, updated_at=? WHERE user_id=? AND provider=?",
            (encrypted, datetime.now(timezone.utc).isoformat(), user_id, provider),
        )

def get_connection(user_id: int) -> dict | None:
    with database() as connection:
        row = connection.execute(
            "SELECT provider, scopes, updated_at FROM mailbox_connections WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

def get_user(user_id: int) -> dict | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

def get_tokens(user_id: int, provider: str) -> dict:
    with database() as connection:
        row = connection.execute("SELECT encrypted_tokens FROM mailbox_connections WHERE user_id=? AND provider=?", (user_id, provider)).fetchone()
    if not row: raise RuntimeError("Mailbox connection not found")
    return json.loads(_fernet().decrypt(row["encrypted_tokens"].encode()).decode())

def disconnect(user_id: int) -> None:
    with database() as connection:
        connection.execute("DELETE FROM mailbox_connections WHERE user_id=?", (user_id,))
        connection.execute("DELETE FROM users WHERE id=?", (user_id,))

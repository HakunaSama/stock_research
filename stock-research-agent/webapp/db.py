"""SQLite data layer — stdlib ``sqlite3`` only, no ORM.

Three tables back the webapp:

    users         — registered accounts (username + salted PBKDF2 password hash)
    sessions      — server-side sessions keyed by an opaque cookie token
    research_jobs — user-initiated ODR runs and their lifecycle

Design choices that matter for a single-instance lightweight server:

* One database file (``STOCK_DB_PATH``, default ``<data>/app.db``). SQLite in
  WAL mode handles our low write volume comfortably.
* ``check_same_thread=False`` + a module-level lock so the FastAPI request
  threads and the background job worker can share one connection safely.
* Passwords are never stored in the clear — PBKDF2-HMAC-SHA256, 200k rounds,
  per-user random salt (stdlib ``hashlib``; no native bcrypt build needed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


# --- password hashing -------------------------------------------------------

_PBKDF2_ROUNDS = 200_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return ``pbkdf2_sha256$<rounds>$<salt_hex>$<hash_hex>``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify a password against a stored PBKDF2 record."""
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(digest, expected)


# --- connection -------------------------------------------------------------

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _db_path() -> str:
    path = os.environ.get("STOCK_DB_PATH")
    if path:
        return os.path.expanduser(path)
    # Default: sit next to the run artifacts data dir.
    data_dir = os.environ.get("STOCK_DATA_DIR", "/tmp/stock-terminal-data")
    return os.path.join(os.path.expanduser(data_dir), "app.db")


def get_conn() -> sqlite3.Connection:
    """Return the shared connection, initialising the schema on first use."""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        path = _db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(conn)
        _conn = conn
        return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT UNIQUE NOT NULL,
            password_hash  TEXT NOT NULL,
            created_at     REAL NOT NULL,
            is_admin       INTEGER NOT NULL DEFAULT 0,
            email          TEXT NOT NULL DEFAULT '',
            email_verified INTEGER NOT NULL DEFAULT 0,
            disabled       INTEGER NOT NULL DEFAULT 0,
            display_name   TEXT NOT NULL DEFAULT '',
            bio            TEXT NOT NULL DEFAULT '',
            avatar_key     TEXT NOT NULL DEFAULT '',
            updated_at     REAL NOT NULL DEFAULT 0,
            last_login_at  REAL
        );

        -- Email verification codes (register / reset password / bind email).
        -- Only the PBKDF2 hash of the code is stored; codes expire and burn
        -- after MAX attempts, so rows are short-lived throwaways.
        CREATE TABLE IF NOT EXISTS email_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            purpose    TEXT NOT NULL,               -- register|reset|bind
            code_hash  TEXT NOT NULL,
            attempts   INTEGER NOT NULL DEFAULT 0,
            used       INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );

        -- Membership subscriptions: one row per user, extended on each
        -- monthly-plan purchase (or by an admin grant). "Active" simply means
        -- expires_at is in the future — no cron needed.
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id    INTEGER PRIMARY KEY,
            plan_code  TEXT NOT NULL DEFAULT '',
            started_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            session_id TEXT UNIQUE NOT NULL,
            user_id    INTEGER NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            user_agent TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Security-relevant account operations. Details intentionally contain
        -- metadata only (never passwords, verification codes, or session tokens).
        CREATE TABLE IF NOT EXISTS account_audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            action     TEXT NOT NULL,
            details    TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS research_jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            target      TEXT NOT NULL,
            question    TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed
            run_id      TEXT NOT NULL DEFAULT '',
            error       TEXT NOT NULL DEFAULT '',
            created_at  REAL NOT NULL,
            started_at  REAL,
            finished_at REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Credits / billing ---------------------------------------------------
        -- One row per user: current point balance + audit counters. The balance
        -- must always equal SUM(credit_ledger.amount) for that user.
        CREATE TABLE IF NOT EXISTS credit_accounts (
            user_id     INTEGER PRIMARY KEY,
            balance     INTEGER NOT NULL DEFAULT 0,
            total_topup INTEGER NOT NULL DEFAULT 0,
            total_spent INTEGER NOT NULL DEFAULT 0,
            updated_at  REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Append-only ledger: the single source of truth for every point move.
        -- Never UPDATE/DELETE rows here; corrections are new rows.
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            amount        INTEGER NOT NULL,           -- +topup/grant/refund, -spend
            balance_after INTEGER NOT NULL,
            reason        TEXT NOT NULL,              -- topup|research_spend|refund|admin_adjust|signup_bonus|plan_grant
            ref_type      TEXT NOT NULL DEFAULT '',   -- order|job|manual
            ref_id        TEXT NOT NULL DEFAULT '',
            memo          TEXT NOT NULL DEFAULT '',
            created_at    REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Top-up orders: one per purchase attempt. out_trade_no is the merchant
        -- order id we hand to a payment provider; UNIQUE makes callbacks idempotent.
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            out_trade_no TEXT UNIQUE NOT NULL,
            user_id      INTEGER NOT NULL,
            plan_code    TEXT NOT NULL,
            credits      INTEGER NOT NULL,            -- points credited on payment
            amount_cents INTEGER NOT NULL,            -- price paid, in cents (avoid floats)
            channel      TEXT NOT NULL DEFAULT 'stub',
            status       TEXT NOT NULL DEFAULT 'pending', -- pending|paid|closed|refunded
            channel_txid TEXT NOT NULL DEFAULT '',
            created_at   REAL NOT NULL,
            paid_at      REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- User strategy library (hot-pluggable research strategies) -----------
        -- Free-text strategies the research pipeline compiles at run time.
        -- At most one row per user has is_active=1; runs fall back to the
        -- built-in demo strategy when a user has no active strategy.
        CREATE TABLE IF NOT EXISTS strategies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            name            TEXT NOT NULL,
            raw_text        TEXT NOT NULL,
            is_active       INTEGER NOT NULL DEFAULT 0,
            is_public       INTEGER NOT NULL DEFAULT 0,
            summary         TEXT NOT NULL DEFAULT '',
            like_count      INTEGER NOT NULL DEFAULT 0,
            favorite_count  INTEGER NOT NULL DEFAULT 0,
            comment_count   INTEGER NOT NULL DEFAULT 0,
            published_at    REAL,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Hashtag-style tags on strategies (hall discovery).
        CREATE TABLE IF NOT EXISTS strategy_tags (
            strategy_id INTEGER NOT NULL,
            tag         TEXT NOT NULL,
            PRIMARY KEY (strategy_id, tag),
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS strategy_likes (
            user_id     INTEGER NOT NULL,
            strategy_id INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            PRIMARY KEY (user_id, strategy_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS strategy_favorites (
            user_id     INTEGER NOT NULL,
            strategy_id INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            PRIMARY KEY (user_id, strategy_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS strategy_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            body        TEXT NOT NULL,
            created_at  REAL NOT NULL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON account_audit_logs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_email_codes ON email_codes(email, purpose, created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_user ON research_jobs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_strategy_tags_tag ON strategy_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_strategy_comments ON strategy_comments(strategy_id, created_at);
        """
    )
    conn.commit()
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for columns introduced after the first release.

    ``ALTER TABLE ... ADD COLUMN`` is a no-op-safe way to bring an existing
    (pre-billing) DB up to date without a heavyweight migration framework.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(research_jobs)")}
    if "credits_cost" not in cols:
        conn.execute("ALTER TABLE research_jobs ADD COLUMN credits_cost INTEGER NOT NULL DEFAULT 0")
    if "charged_credits" not in cols:
        # Points actually deducted (0 when covered by the free daily quota).
        conn.execute("ALTER TABLE research_jobs ADD COLUMN charged_credits INTEGER NOT NULL DEFAULT 0")
    if "refunded" not in cols:
        conn.execute("ALTER TABLE research_jobs ADD COLUMN refunded INTEGER NOT NULL DEFAULT 0")
    if "strategy_id" not in cols:
        # Which library strategy the run was enqueued with (0 = built-in demo).
        conn.execute("ALTER TABLE research_jobs ADD COLUMN strategy_id INTEGER NOT NULL DEFAULT 0")
    if "strategy_name" not in cols:
        # Denormalized for display: survives later edits/deletes of the strategy.
        conn.execute("ALTER TABLE research_jobs ADD COLUMN strategy_name TEXT NOT NULL DEFAULT ''")

    ucols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if "email" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
    if "email_verified" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
    if "disabled" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
    if "display_name" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
    if "bio" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
    if "avatar_key" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_key TEXT NOT NULL DEFAULT ''")
    if "updated_at" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN updated_at REAL NOT NULL DEFAULT 0")
    if "last_login_at" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN last_login_at REAL")
    # Unique on non-empty emails only, so legacy username-only accounts (email
    # = '') can coexist until they bind one.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email != ''"
    )

    session_cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "session_id" not in session_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
    if "last_seen_at" not in session_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN last_seen_at REAL NOT NULL DEFAULT 0")
    if "user_agent" not in session_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_agent TEXT NOT NULL DEFAULT ''")
    if "ip_address" not in session_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN ip_address TEXT NOT NULL DEFAULT ''")
    for row in conn.execute("SELECT token FROM sessions WHERE session_id = ''").fetchall():
        conn.execute(
            "UPDATE sessions SET session_id = ?, last_seen_at = created_at WHERE token = ?",
            (secrets.token_urlsafe(12), row["token"]),
        )
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_id ON sessions(session_id)")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            action     TEXT NOT NULL,
            details    TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_audit_user ON account_audit_logs(user_id, created_at);
        """
    )

    # Strategy hall: publish flag, summary, engagement counters + social tables.
    scols = {r["name"] for r in conn.execute("PRAGMA table_info(strategies)")}
    for col, ddl in [
        ("is_public", "ALTER TABLE strategies ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0"),
        ("summary", "ALTER TABLE strategies ADD COLUMN summary TEXT NOT NULL DEFAULT ''"),
        ("like_count", "ALTER TABLE strategies ADD COLUMN like_count INTEGER NOT NULL DEFAULT 0"),
        ("favorite_count", "ALTER TABLE strategies ADD COLUMN favorite_count INTEGER NOT NULL DEFAULT 0"),
        ("comment_count", "ALTER TABLE strategies ADD COLUMN comment_count INTEGER NOT NULL DEFAULT 0"),
        ("published_at", "ALTER TABLE strategies ADD COLUMN published_at REAL"),
    ]:
        if col not in scols:
            conn.execute(ddl)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS strategy_tags (
            strategy_id INTEGER NOT NULL,
            tag         TEXT NOT NULL,
            PRIMARY KEY (strategy_id, tag),
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS strategy_likes (
            user_id     INTEGER NOT NULL,
            strategy_id INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            PRIMARY KEY (user_id, strategy_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS strategy_favorites (
            user_id     INTEGER NOT NULL,
            strategy_id INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            PRIMARY KEY (user_id, strategy_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS strategy_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            body        TEXT NOT NULL,
            created_at  REAL NOT NULL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_strategies_public ON strategies(is_public, published_at);
        CREATE INDEX IF NOT EXISTS idx_strategy_tags_tag ON strategy_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_strategy_comments ON strategy_comments(strategy_id, created_at);
        """
    )
    conn.commit()


# --- users ------------------------------------------------------------------


def create_user(
    username: str, password: str, is_admin: bool = False,
    email: str = "", email_verified: bool = False,
) -> Dict[str, Any]:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at, is_admin, email, email_verified) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, hash_password(password), time.time(), 1 if is_admin else 0,
             email, 1 if email_verified else 0),
        )
        conn.commit()
        uid = cur.lastrowid
    return {"id": uid, "username": username, "is_admin": is_admin, "email": email}


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cur.fetchone()


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    if not email:
        return None
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cur.fetchone()


def set_user_password(user_id: int, new_password: str) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()


def set_user_email(user_id: int, email: str, verified: bool = True) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET email = ?, email_verified = ? WHERE id = ?",
            (email, 1 if verified else 0, user_id),
        )
        conn.commit()


def update_user_profile(
    user_id: int, username: str, display_name: str, bio: str,
) -> Optional[sqlite3.Row]:
    """Update public profile fields atomically with case-insensitive username
    uniqueness. The module lock makes the check-and-update race-free on SQLite."""
    conn = get_conn()
    with _lock:
        conflict = conn.execute(
            "SELECT id FROM users WHERE lower(username) = lower(?) AND id != ?",
            (username, user_id),
        ).fetchone()
        if conflict is not None:
            return None
        conn.execute(
            "UPDATE users SET username = ?, display_name = ?, bio = ?, updated_at = ? WHERE id = ?",
            (username, display_name, bio, time.time(), user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def set_user_avatar(user_id: int, avatar_key: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET avatar_key = ?, updated_at = ? WHERE id = ?",
            (avatar_key, time.time(), user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def mark_user_login(user_id: int) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET last_login_at = ?, updated_at = CASE WHEN updated_at = 0 THEN ? ELSE updated_at END WHERE id = ?",
            (time.time(), time.time(), user_id),
        )
        conn.commit()


def set_user_disabled(user_id: int, disabled: bool) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET disabled = ? WHERE id = ?",
            (1 if disabled else 0, user_id),
        )
        if disabled:
            # Kick a banned user out immediately — their sessions die with them.
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()


def revoke_user_sessions(user_id: int, keep_token: str = "") -> None:
    """Log the user out everywhere (e.g. after a password change), optionally
    keeping the session that performed the change."""
    conn = get_conn()
    with _lock:
        if keep_token:
            conn.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token != ?",
                (user_id, keep_token),
            )
        else:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()


def count_users() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]


def set_user_admin(user_id: int, is_admin: bool) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (1 if is_admin else 0, user_id),
        )
        conn.commit()


# --- sessions ---------------------------------------------------------------


def create_session(
    user_id: int, ttl_seconds: int, user_agent: str = "", ip_address: str = "",
) -> str:
    token = secrets.token_urlsafe(32)
    session_id = secrets.token_urlsafe(12)
    now = time.time()
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO sessions "
            "(token, session_id, user_id, created_at, expires_at, last_seen_at, user_agent, ip_address) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (token, session_id, user_id, now, now + ttl_seconds, now,
             user_agent[:300], ip_address[:64]),
        )
        conn.commit()
    return token


def get_session_user(token: str) -> Optional[sqlite3.Row]:
    """Return the user row for a live session token, or None if invalid/expired."""
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < time.time():
        delete_session(token)
        return None
    user = get_user_by_id(row["user_id"])
    if user is not None and user["disabled"]:
        return None  # banned accounts hold no live sessions
    now = time.time()
    if now - (row["last_seen_at"] or 0) >= 300:
        with _lock:
            conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token = ?", (now, token))
            conn.commit()
    return user


def list_user_sessions(user_id: int) -> List[sqlite3.Row]:
    now = time.time()
    conn = get_conn()
    return conn.execute(
        "SELECT session_id, created_at, expires_at, last_seen_at, user_agent, ip_address "
        "FROM sessions WHERE user_id = ? AND expires_at >= ? ORDER BY last_seen_at DESC",
        (user_id, now),
    ).fetchall()


def delete_user_session(user_id: int, session_id: str) -> bool:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id),
        )
        conn.commit()
        return cur.rowcount > 0


def session_id_for_token(token: str) -> str:
    if not token:
        return ""
    row = get_conn().execute(
        "SELECT session_id FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    return row["session_id"] if row else ""


def add_account_audit(
    user_id: int, action: str, details: Optional[Dict[str, Any]] = None,
    ip_address: str = "", user_agent: str = "",
) -> None:
    conn = get_conn()
    payload = json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"))
    with _lock:
        conn.execute(
            "INSERT INTO account_audit_logs "
            "(user_id, action, details, ip_address, user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action[:64], payload[:2000], ip_address[:64], user_agent[:300], time.time()),
        )
        conn.commit()


def delete_session(token: str) -> None:
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def purge_expired_sessions() -> None:
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        conn.commit()


# --- email verification codes -------------------------------------------------
#
# Flow: create_email_code() when sending, verify_email_code() when the user
# submits. Codes are stored hashed (same PBKDF2 as passwords), single-use,
# TTL-bound and burned after too many wrong attempts. Rate limiting (resend
# interval + daily cap) is enforced by the callers via the query helpers.

EMAIL_CODE_MAX_ATTEMPTS = 5


def create_email_code(email: str, purpose: str, code: str, ttl_seconds: int) -> None:
    now = time.time()
    conn = get_conn()
    with _lock:
        # A fresh code supersedes previous outstanding ones for this email+purpose.
        conn.execute(
            "UPDATE email_codes SET used = 1 WHERE email = ? AND purpose = ? AND used = 0",
            (email, purpose),
        )
        conn.execute(
            "INSERT INTO email_codes (email, purpose, code_hash, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (email, purpose, hash_password(code), now, now + ttl_seconds),
        )
        # Opportunistic cleanup — dead codes have no value.
        conn.execute("DELETE FROM email_codes WHERE expires_at < ?", (now - 86400,))
        conn.commit()


def verify_email_code(email: str, purpose: str, code: str) -> bool:
    """Check-and-consume the latest outstanding code. Wrong guesses count up;
    the code burns after EMAIL_CODE_MAX_ATTEMPTS. Success marks it used."""
    now = time.time()
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT * FROM email_codes WHERE email = ? AND purpose = ? AND used = 0 "
            "AND expires_at > ? ORDER BY id DESC LIMIT 1",
            (email, purpose, now),
        ).fetchone()
        if row is None:
            return False
        if row["attempts"] >= EMAIL_CODE_MAX_ATTEMPTS:
            conn.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            return False
        if verify_password(code, row["code_hash"]):
            conn.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            return True
        conn.execute(
            "UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],)
        )
        conn.commit()
        return False


def seconds_until_resend(email: str, purpose: str, min_interval: int) -> int:
    """0 when a new code may be sent now, else remaining cooldown seconds."""
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(created_at) AS ts FROM email_codes WHERE email = ? AND purpose = ?",
        (email, purpose),
    ).fetchone()
    if not row or row["ts"] is None:
        return 0
    remain = int(row["ts"] + min_interval - time.time())
    return max(0, remain)


def count_email_codes_today(email: str) -> int:
    conn = get_conn()
    day_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    return conn.execute(
        "SELECT COUNT(*) AS c FROM email_codes WHERE email = ? AND created_at >= ?",
        (email, day_start),
    ).fetchone()["c"]


# --- subscriptions ------------------------------------------------------------


def get_subscription(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
    ).fetchone()


def subscription_active(user_id: int) -> bool:
    row = get_subscription(user_id)
    return bool(row and row["expires_at"] > time.time())


def extend_subscription(user_id: int, plan_code: str, days: int) -> float:
    """Add ``days`` of membership. Extension stacks on the current expiry when
    still active (renewing early never wastes paid days). Returns new expiry."""
    now = time.time()
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
        base = row["expires_at"] if row and row["expires_at"] > now else now
        new_expiry = base + days * 86400
        if row is None:
            conn.execute(
                "INSERT INTO subscriptions (user_id, plan_code, started_at, expires_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, plan_code, now, new_expiry, now),
            )
        else:
            conn.execute(
                "UPDATE subscriptions SET plan_code = ?, expires_at = ?, updated_at = ? "
                "WHERE user_id = ?",
                (plan_code, new_expiry, now, user_id),
            )
        conn.commit()
        return new_expiry


# --- research jobs ----------------------------------------------------------


def create_job(
    user_id: int, target: str, question: str,
    credits_cost: int = 0, charged_credits: int = 0,
    strategy_id: int = 0, strategy_name: str = "",
) -> int:
    """Persist a new research job.

    ``credits_cost``   — the run's list price in points (for the record).
    ``charged_credits``— points actually deducted (0 when a free-quota run);
                         this is what a refund gives back on our-side failure.
    ``strategy_id``    — library strategy the run uses (0 = built-in demo).
    """
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO research_jobs (user_id, target, question, status, created_at, "
            "credits_cost, charged_credits, strategy_id, strategy_name) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
            (user_id, target, question, time.time(), credits_cost, charged_credits,
             strategy_id, strategy_name),
        )
        conn.commit()
        return cur.lastrowid


def refund_job(job_id: int) -> Optional[int]:
    """Refund a failed job's charged points, at most once (``refunded`` CAS).

    Returns the refunded amount (>=0) on the first call, or None if the job was
    already refunded / not found / was a free run (nothing charged)."""
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT user_id, charged_credits, refunded FROM research_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None or row["refunded"] or row["charged_credits"] <= 0:
            return None
        cur = conn.execute(
            "UPDATE research_jobs SET refunded = 1 WHERE id = ? AND refunded = 0",
            (job_id,),
        )
        if cur.rowcount == 0:
            return None  # someone else refunded it first
        amount = int(row["charged_credits"])
        _change_credits(
            conn, row["user_id"], amount, "refund", "job", str(job_id),
            "研究失败自动退点", require_sufficient=False,
        )
        conn.commit()
        return amount


def update_job(job_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    conn = get_conn()
    with _lock:
        conn.execute(f"UPDATE research_jobs SET {cols} WHERE id = ?", vals)
        conn.commit()


def get_job(job_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute("SELECT * FROM research_jobs WHERE id = ?", (job_id,)).fetchone()


def list_jobs_for_user(user_id: int, limit: int = 50) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM research_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def count_jobs_since(user_id: int, since_ts: float) -> int:
    """Count a user's jobs created after ``since_ts`` (for daily quota)."""
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) AS c FROM research_jobs WHERE user_id = ? AND created_at >= ?",
        (user_id, since_ts),
    ).fetchone()["c"]


def count_free_jobs_since(user_id: int, since_ts: float) -> int:
    """Count a user's FREE runs (charged 0 points) today, excluding failed ones.

    This is what the daily free quota is measured against — a paid run or a run
    that failed on our side does not eat into the free allowance."""
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) AS c FROM research_jobs "
        "WHERE user_id = ? AND created_at >= ? AND charged_credits = 0 "
        "AND status != 'failed'",
        (user_id, since_ts),
    ).fetchone()["c"]


def list_pending_jobs() -> List[sqlite3.Row]:
    """Jobs left in pending/running at startup (for crash recovery re-queue)."""
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM research_jobs WHERE status IN ('pending', 'running') ORDER BY created_at"
    ).fetchall()


# --- strategy library + hall --------------------------------------------------
#
# Personal library: each user owns strategies; at most one is_active=1.
# Hall: is_public=1 strategies are discoverable; likes / favorites / comments
# are separate tables with denormalized counters on the strategy row.

_TAG_RE = re.compile(r"^[\w\u4e00-\u9fff-]{1,20}$", re.UNICODE)
_HASHTAG_RE = re.compile(r"(?:^|[\s,，、])#([\w\u4e00-\u9fff-]{1,20})", re.UNICODE)


def normalize_tags(tags: List[str], limit: int = 8) -> List[str]:
    """Strip #, validate, de-dupe (case-insensitive), cap length."""
    out: List[str] = []
    seen: set[str] = set()
    for raw in tags:
        t = (raw or "").strip().lstrip("#")
        if not t or not _TAG_RE.match(t):
            continue
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def extract_hashtags(text: str, limit: int = 8) -> List[str]:
    return normalize_tags(_HASHTAG_RE.findall(text or ""), limit=limit)


def list_strategies(user_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM strategies WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()


def count_strategies(user_id: int) -> int:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) AS c FROM strategies WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]


def get_strategy(strategy_id: int, user_id: int) -> Optional[sqlite3.Row]:
    """Fetch a strategy, scoped to its owner (no cross-user reads)."""
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM strategies WHERE id = ? AND user_id = ?",
        (strategy_id, user_id),
    ).fetchone()


def get_strategy_row(strategy_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
    ).fetchone()


def get_active_strategy(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM strategies WHERE user_id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


def get_strategy_tags(strategy_id: int) -> List[str]:
    conn = get_conn()
    return [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM strategy_tags WHERE strategy_id = ? ORDER BY tag",
            (strategy_id,),
        ).fetchall()
    ]


def get_strategies_tags_map(strategy_ids: List[int]) -> Dict[int, List[str]]:
    if not strategy_ids:
        return {}
    conn = get_conn()
    placeholders = ",".join("?" * len(strategy_ids))
    rows = conn.execute(
        f"SELECT strategy_id, tag FROM strategy_tags WHERE strategy_id IN ({placeholders}) "
        "ORDER BY tag",
        strategy_ids,
    ).fetchall()
    out: Dict[int, List[str]] = {sid: [] for sid in strategy_ids}
    for r in rows:
        out[r["strategy_id"]].append(r["tag"])
    return out


def _set_strategy_tags(conn: sqlite3.Connection, strategy_id: int, tags: List[str]) -> None:
    conn.execute("DELETE FROM strategy_tags WHERE strategy_id = ?", (strategy_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO strategy_tags (strategy_id, tag) VALUES (?, ?)",
            (strategy_id, tag),
        )


def create_strategy(
    user_id: int, name: str, raw_text: str, activate: bool = False,
    summary: str = "", tags: Optional[List[str]] = None,
) -> int:
    now = time.time()
    tags = normalize_tags(tags or [])
    conn = get_conn()
    with _lock:
        if activate:
            conn.execute(
                "UPDATE strategies SET is_active = 0 WHERE user_id = ?", (user_id,)
            )
        cur = conn.execute(
            "INSERT INTO strategies (user_id, name, raw_text, is_active, summary, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, raw_text, 1 if activate else 0, summary, now, now),
        )
        sid = cur.lastrowid
        _set_strategy_tags(conn, sid, tags)
        conn.commit()
        return sid


def update_strategy(
    strategy_id: int, user_id: int, name: str, raw_text: str,
    summary: Optional[str] = None, tags: Optional[List[str]] = None,
) -> bool:
    """Edit an owned strategy in place. Returns False if not found / not owned."""
    conn = get_conn()
    with _lock:
        if summary is None:
            cur = conn.execute(
                "UPDATE strategies SET name = ?, raw_text = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?",
                (name, raw_text, time.time(), strategy_id, user_id),
            )
        else:
            cur = conn.execute(
                "UPDATE strategies SET name = ?, raw_text = ?, summary = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?",
                (name, raw_text, summary, time.time(), strategy_id, user_id),
            )
        if cur.rowcount == 0:
            conn.rollback()
            return False
        if tags is not None:
            _set_strategy_tags(conn, strategy_id, normalize_tags(tags))
        conn.commit()
        return True


def delete_strategy(strategy_id: int, user_id: int) -> bool:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "DELETE FROM strategies WHERE id = ? AND user_id = ?",
            (strategy_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_active_strategy(user_id: int, strategy_id: int) -> bool:
    """Make ``strategy_id`` the user's active strategy (single-choice).

    ``strategy_id = 0`` deactivates all — the built-in demo strategy applies.
    Returns False when a non-zero id isn't an owned strategy (nothing changes).
    """
    conn = get_conn()
    with _lock:
        if strategy_id:
            owned = conn.execute(
                "SELECT 1 FROM strategies WHERE id = ? AND user_id = ?",
                (strategy_id, user_id),
            ).fetchone()
            if owned is None:
                return False
        conn.execute(
            "UPDATE strategies SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        if strategy_id:
            conn.execute(
                "UPDATE strategies SET is_active = 1, updated_at = ? WHERE id = ?",
                (time.time(), strategy_id),
            )
        conn.commit()
        return True


def publish_strategy(
    strategy_id: int, user_id: int, is_public: bool,
    tags: Optional[List[str]] = None, summary: Optional[str] = None,
) -> bool:
    """Publish / unpublish a strategy to the hall. Optionally refresh tags/summary."""
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT id, published_at FROM strategies WHERE id = ? AND user_id = ?",
            (strategy_id, user_id),
        ).fetchone()
        if row is None:
            return False
        now = time.time()
        if is_public:
            published_at = row["published_at"] or now
            if summary is not None:
                conn.execute(
                    "UPDATE strategies SET is_public = 1, published_at = ?, summary = ?, "
                    "updated_at = ? WHERE id = ?",
                    (published_at, summary, now, strategy_id),
                )
            else:
                conn.execute(
                    "UPDATE strategies SET is_public = 1, published_at = ?, updated_at = ? "
                    "WHERE id = ?",
                    (published_at, now, strategy_id),
                )
        else:
            conn.execute(
                "UPDATE strategies SET is_public = 0, updated_at = ? WHERE id = ?",
                (now, strategy_id),
            )
        if tags is not None:
            _set_strategy_tags(conn, strategy_id, normalize_tags(tags))
        conn.commit()
        return True


def list_hall_strategies(
    *,
    viewer_id: int,
    tag: str = "",
    q: str = "",
    sort: str = "hot",
    limit: int = 30,
    offset: int = 0,
) -> List[sqlite3.Row]:
    """Public strategies for the hall, with viewer like/favorite flags."""
    conn = get_conn()
    where = ["s.is_public = 1"]
    params: list = []
    if tag:
        where.append(
            "EXISTS (SELECT 1 FROM strategy_tags t WHERE t.strategy_id = s.id AND t.tag = ?)"
        )
        params.append(tag.lstrip("#"))
    if q:
        where.append("(s.name LIKE ? OR s.raw_text LIKE ? OR s.summary LIKE ? OR u.username LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like, like]
    order = {
        "new": "s.published_at DESC, s.id DESC",
        "likes": "s.like_count DESC, s.published_at DESC",
        "comments": "s.comment_count DESC, s.published_at DESC",
        "hot": "(s.like_count * 3 + s.favorite_count * 2 + s.comment_count) DESC, s.published_at DESC",
    }.get(sort, "(s.like_count * 3 + s.favorite_count * 2 + s.comment_count) DESC, s.published_at DESC")
    sql = (
        "SELECT s.*, u.username AS author_name, "
        "EXISTS(SELECT 1 FROM strategy_likes l WHERE l.strategy_id = s.id AND l.user_id = ?) AS liked, "
        "EXISTS(SELECT 1 FROM strategy_favorites f WHERE f.strategy_id = s.id AND f.user_id = ?) AS favorited "
        f"FROM strategies s JOIN users u ON u.id = s.user_id "
        f"WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
    )
    params = [viewer_id, viewer_id] + params + [limit, offset]
    return conn.execute(sql, params).fetchall()


def get_hall_strategy(strategy_id: int, viewer_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT s.*, u.username AS author_name, "
        "EXISTS(SELECT 1 FROM strategy_likes l WHERE l.strategy_id = s.id AND l.user_id = ?) AS liked, "
        "EXISTS(SELECT 1 FROM strategy_favorites f WHERE f.strategy_id = s.id AND f.user_id = ?) AS favorited "
        "FROM strategies s JOIN users u ON u.id = s.user_id "
        "WHERE s.id = ? AND (s.is_public = 1 OR s.user_id = ?)",
        (viewer_id, viewer_id, strategy_id, viewer_id),
    ).fetchone()


def list_popular_tags(limit: int = 40) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT t.tag AS tag, COUNT(*) AS count FROM strategy_tags t "
        "JOIN strategies s ON s.id = t.strategy_id AND s.is_public = 1 "
        "GROUP BY t.tag ORDER BY count DESC, t.tag LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"tag": r["tag"], "count": r["count"]} for r in rows]


def toggle_like(user_id: int, strategy_id: int) -> Optional[Dict[str, Any]]:
    """Like / unlike a public strategy. Returns {liked, like_count} or None."""
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT id, is_public, like_count FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        if row is None or not row["is_public"]:
            return None
        existing = conn.execute(
            "SELECT 1 FROM strategy_likes WHERE user_id = ? AND strategy_id = ?",
            (user_id, strategy_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM strategy_likes WHERE user_id = ? AND strategy_id = ?",
                (user_id, strategy_id),
            )
            conn.execute(
                "UPDATE strategies SET like_count = MAX(0, like_count - 1) WHERE id = ?",
                (strategy_id,),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO strategy_likes (user_id, strategy_id, created_at) VALUES (?, ?, ?)",
                (user_id, strategy_id, time.time()),
            )
            conn.execute(
                "UPDATE strategies SET like_count = like_count + 1 WHERE id = ?",
                (strategy_id,),
            )
            liked = True
        count = conn.execute(
            "SELECT like_count FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()["like_count"]
        conn.commit()
        return {"liked": liked, "like_count": int(count)}


def toggle_favorite(user_id: int, strategy_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT id, is_public, favorite_count FROM strategies WHERE id = ?",
            (strategy_id,),
        ).fetchone()
        if row is None or not row["is_public"]:
            return None
        existing = conn.execute(
            "SELECT 1 FROM strategy_favorites WHERE user_id = ? AND strategy_id = ?",
            (user_id, strategy_id),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM strategy_favorites WHERE user_id = ? AND strategy_id = ?",
                (user_id, strategy_id),
            )
            conn.execute(
                "UPDATE strategies SET favorite_count = MAX(0, favorite_count - 1) WHERE id = ?",
                (strategy_id,),
            )
            favorited = False
        else:
            conn.execute(
                "INSERT INTO strategy_favorites (user_id, strategy_id, created_at) VALUES (?, ?, ?)",
                (user_id, strategy_id, time.time()),
            )
            conn.execute(
                "UPDATE strategies SET favorite_count = favorite_count + 1 WHERE id = ?",
                (strategy_id,),
            )
            favorited = True
        count = conn.execute(
            "SELECT favorite_count FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()["favorite_count"]
        conn.commit()
        return {"favorited": favorited, "favorite_count": int(count)}


def list_favorite_strategies(user_id: int, limit: int = 50) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT s.*, u.username AS author_name, 1 AS favorited, "
        "EXISTS(SELECT 1 FROM strategy_likes l WHERE l.strategy_id = s.id AND l.user_id = ?) AS liked "
        "FROM strategy_favorites f "
        "JOIN strategies s ON s.id = f.strategy_id AND s.is_public = 1 "
        "JOIN users u ON u.id = s.user_id "
        "WHERE f.user_id = ? ORDER BY f.created_at DESC LIMIT ?",
        (user_id, user_id, limit),
    ).fetchall()


def list_comments(strategy_id: int, limit: int = 100) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT c.*, u.username FROM strategy_comments c "
        "JOIN users u ON u.id = c.user_id "
        "WHERE c.strategy_id = ? ORDER BY c.created_at DESC LIMIT ?",
        (strategy_id, limit),
    ).fetchall()


def add_comment(strategy_id: int, user_id: int, body: str) -> Optional[int]:
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT id, is_public FROM strategies WHERE id = ?", (strategy_id,)
        ).fetchone()
        if row is None or not row["is_public"]:
            return None
        cur = conn.execute(
            "INSERT INTO strategy_comments (strategy_id, user_id, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (strategy_id, user_id, body, time.time()),
        )
        conn.execute(
            "UPDATE strategies SET comment_count = comment_count + 1 WHERE id = ?",
            (strategy_id,),
        )
        conn.commit()
        return cur.lastrowid


def delete_comment(comment_id: int, user_id: int, is_admin: bool = False) -> bool:
    conn = get_conn()
    with _lock:
        row = conn.execute(
            "SELECT id, strategy_id, user_id FROM strategy_comments WHERE id = ?",
            (comment_id,),
        ).fetchone()
        if row is None:
            return False
        if row["user_id"] != user_id and not is_admin:
            return False
        conn.execute("DELETE FROM strategy_comments WHERE id = ?", (comment_id,))
        conn.execute(
            "UPDATE strategies SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
            (row["strategy_id"],),
        )
        conn.commit()
        return True


def adopt_strategy(source_id: int, user_id: int, activate: bool = False) -> Optional[int]:
    """Copy a public strategy into the viewer's personal library."""
    conn = get_conn()
    with _lock:
        src = conn.execute(
            "SELECT * FROM strategies WHERE id = ? AND is_public = 1", (source_id,)
        ).fetchone()
        if src is None:
            return None
        if src["user_id"] == user_id:
            # Already own it — just optionally activate.
            if activate:
                conn.execute("UPDATE strategies SET is_active = 0 WHERE user_id = ?", (user_id,))
                conn.execute(
                    "UPDATE strategies SET is_active = 1, updated_at = ? WHERE id = ?",
                    (time.time(), source_id),
                )
                conn.commit()
            return source_id
        tags = [
            r["tag"]
            for r in conn.execute(
                "SELECT tag FROM strategy_tags WHERE strategy_id = ?", (source_id,)
            ).fetchall()
        ]
        now = time.time()
        if activate:
            conn.execute("UPDATE strategies SET is_active = 0 WHERE user_id = ?", (user_id,))
        name = src["name"]
        if len(name) > 36:
            name = name[:36]
        name = f"{name}·副本"
        cur = conn.execute(
            "INSERT INTO strategies (user_id, name, raw_text, is_active, summary, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, src["raw_text"], 1 if activate else 0,
             src["summary"] or "", now, now),
        )
        sid = cur.lastrowid
        _set_strategy_tags(conn, sid, tags)
        conn.commit()
        return sid


# --- credits / billing ------------------------------------------------------
#
# Invariant: credit_accounts.balance == SUM(credit_ledger.amount) per user.
# Every balance change goes through _change_credits so the ledger and the
# cached balance move together in one transaction. The module-level _lock
# already serializes all writes (single process, single connection), so the
# `WHERE balance >= ?` conditional update below cannot be beaten by a race.


def ensure_account(user_id: int) -> None:
    """Create the user's credit account row if it doesn't exist yet."""
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT OR IGNORE INTO credit_accounts (user_id, balance, updated_at) "
            "VALUES (?, 0, ?)",
            (user_id, time.time()),
        )
        conn.commit()


def get_balance(user_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT balance FROM credit_accounts WHERE user_id = ?", (user_id,)
    ).fetchone()
    return int(row["balance"]) if row else 0


def get_account(user_id: int) -> Dict[str, int]:
    conn = get_conn()
    row = conn.execute(
        "SELECT balance, total_topup, total_spent FROM credit_accounts WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return {"balance": 0, "total_topup": 0, "total_spent": 0}
    return {
        "balance": int(row["balance"]),
        "total_topup": int(row["total_topup"]),
        "total_spent": int(row["total_spent"]),
    }


def _change_credits(
    conn: sqlite3.Connection,
    user_id: int,
    delta: int,
    reason: str,
    ref_type: str = "",
    ref_id: str = "",
    memo: str = "",
    require_sufficient: bool = True,
) -> Optional[int]:
    """Atomically move a user's balance by ``delta`` and append a ledger row.

    MUST be called while holding ``_lock``. Returns the new balance, or None if
    ``delta`` is negative, ``require_sufficient`` is set, and the balance is too
    low (caller should treat None as "insufficient credits" and not commit).
    """
    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO credit_accounts (user_id, balance, updated_at) VALUES (?, 0, ?)",
        (user_id, now),
    )
    if delta < 0 and require_sufficient:
        cur = conn.execute(
            "UPDATE credit_accounts SET balance = balance + ?, "
            "total_spent = total_spent + ?, updated_at = ? "
            "WHERE user_id = ? AND balance >= ?",
            (delta, -delta, now, user_id, -delta),
        )
        if cur.rowcount == 0:
            return None  # insufficient balance
    else:
        topup_inc = delta if delta > 0 else 0
        spent_inc = -delta if delta < 0 else 0
        conn.execute(
            "UPDATE credit_accounts SET balance = balance + ?, "
            "total_topup = total_topup + ?, total_spent = total_spent + ?, updated_at = ? "
            "WHERE user_id = ?",
            (delta, topup_inc, spent_inc, now, user_id),
        )
    new_balance = int(
        conn.execute(
            "SELECT balance FROM credit_accounts WHERE user_id = ?", (user_id,)
        ).fetchone()["balance"]
    )
    conn.execute(
        "INSERT INTO credit_ledger "
        "(user_id, amount, balance_after, reason, ref_type, ref_id, memo, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, delta, new_balance, reason, ref_type, ref_id, memo, now),
    )
    return new_balance


def add_credits(
    user_id: int, amount: int, reason: str, ref_type: str = "", ref_id: str = "", memo: str = ""
) -> int:
    """Grant points (topup / plan grant / signup bonus / admin add). Returns new balance."""
    conn = get_conn()
    with _lock:
        new_balance = _change_credits(
            conn, user_id, abs(amount), reason, ref_type, ref_id, memo, require_sufficient=False
        )
        conn.commit()
    return int(new_balance)


def adjust_credits(user_id: int, delta: int, memo: str = "") -> Optional[int]:
    """Admin manual adjust (delta may be +/-). Returns new balance, or None if
    a negative adjust would overdraw the account."""
    conn = get_conn()
    with _lock:
        new_balance = _change_credits(
            conn, user_id, delta, "admin_adjust", "manual", "", memo,
            require_sufficient=delta < 0,
        )
        if new_balance is None:
            conn.rollback()
            return None
        conn.commit()
    return new_balance


def spend_credits(
    user_id: int, amount: int, reason: str, ref_type: str = "", ref_id: str = "", memo: str = ""
) -> Optional[int]:
    """Deduct ``amount`` points if the balance covers it. Returns the new
    balance, or None if insufficient (nothing is written)."""
    if amount <= 0:
        return get_balance(user_id)
    conn = get_conn()
    with _lock:
        new_balance = _change_credits(
            conn, user_id, -abs(amount), reason, ref_type, ref_id, memo, require_sufficient=True
        )
        if new_balance is None:
            conn.rollback()
            return None
        conn.commit()
    return new_balance


def list_ledger(user_id: int, limit: int = 100) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM credit_ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def list_all_ledger(limit: int = 200) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM credit_ledger ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# --- orders -----------------------------------------------------------------


def create_order(
    out_trade_no: str, user_id: int, plan_code: str, credits: int,
    amount_cents: int, channel: str = "stub",
) -> int:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO orders (out_trade_no, user_id, plan_code, credits, "
            "amount_cents, channel, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (out_trade_no, user_id, plan_code, credits, amount_cents, channel, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def get_order(out_trade_no: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
    ).fetchone()


def mark_order_paid(out_trade_no: str, channel_txid: str = "") -> Optional[sqlite3.Row]:
    """Idempotently settle an order and credit the user in ONE transaction.

    The ``status = 'pending'`` guard is a compare-and-swap: a duplicate payment
    callback finds 0 rows to update and credits nothing. Returns the paid order
    row on the transition, or None if it was already settled / not found.
    """
    conn = get_conn()
    with _lock:
        order = conn.execute(
            "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
        ).fetchone()
        if order is None:
            return None
        cur = conn.execute(
            "UPDATE orders SET status = 'paid', paid_at = ?, channel_txid = ? "
            "WHERE out_trade_no = ? AND status = 'pending'",
            (time.time(), channel_txid, out_trade_no),
        )
        if cur.rowcount == 0:
            return None  # already settled — do not double-credit
        _change_credits(
            conn, order["user_id"], abs(order["credits"]), "topup",
            "order", out_trade_no, f"充值 {order['plan_code']}", require_sufficient=False,
        )
        conn.commit()
        return conn.execute(
            "SELECT * FROM orders WHERE out_trade_no = ?", (out_trade_no,)
        ).fetchone()


def list_orders_for_user(user_id: int, limit: int = 50) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def list_all_orders(limit: int = 200, status: Optional[str] = None) -> List[sqlite3.Row]:
    conn = get_conn()
    if status:
        return conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


# --- admin views ------------------------------------------------------------


def list_users_with_balance(limit: int = 500, q: str = "") -> List[sqlite3.Row]:
    conn = get_conn()
    sql = (
        "SELECT u.id, u.username, u.email, u.email_verified, u.disabled, "
        "u.is_admin, u.created_at, "
        "COALESCE(a.balance, 0) AS balance, "
        "COALESCE(a.total_topup, 0) AS total_topup, "
        "COALESCE(a.total_spent, 0) AS total_spent, "
        "s.expires_at AS sub_expires_at "
        "FROM users u "
        "LEFT JOIN credit_accounts a ON a.user_id = u.id "
        "LEFT JOIN subscriptions s ON s.user_id = u.id "
    )
    params: list = []
    if q:
        sql += "WHERE u.username LIKE ? OR u.email LIKE ? "
        like = f"%{q}%"
        params += [like, like]
    sql += "ORDER BY u.id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def admin_stats() -> Dict[str, Any]:
    """Aggregate counters for the admin overview dashboard."""
    conn = get_conn()
    day_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    q = conn.execute
    return {
        "total_users": q("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "total_jobs": q("SELECT COUNT(*) c FROM research_jobs").fetchone()["c"],
        "jobs_today": q(
            "SELECT COUNT(*) c FROM research_jobs WHERE created_at >= ?", (day_start,)
        ).fetchone()["c"],
        "jobs_running": q(
            "SELECT COUNT(*) c FROM research_jobs WHERE status IN ('pending','running')"
        ).fetchone()["c"],
        "paid_orders": q("SELECT COUNT(*) c FROM orders WHERE status='paid'").fetchone()["c"],
        "revenue_cents": q(
            "SELECT COALESCE(SUM(amount_cents),0) s FROM orders WHERE status='paid'"
        ).fetchone()["s"],
        "revenue_today_cents": q(
            "SELECT COALESCE(SUM(amount_cents),0) s FROM orders WHERE status='paid' AND paid_at >= ?",
            (day_start,),
        ).fetchone()["s"],
        "credits_outstanding": q(
            "SELECT COALESCE(SUM(balance),0) s FROM credit_accounts"
        ).fetchone()["s"],
        "active_subscriptions": q(
            "SELECT COUNT(*) c FROM subscriptions WHERE expires_at > ?", (time.time(),)
        ).fetchone()["c"],
        "verified_users": q(
            "SELECT COUNT(*) c FROM users WHERE email_verified = 1"
        ).fetchone()["c"],
        "disabled_users": q(
            "SELECT COUNT(*) c FROM users WHERE disabled = 1"
        ).fetchone()["c"],
    }

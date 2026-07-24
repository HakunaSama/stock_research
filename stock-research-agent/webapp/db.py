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
import os
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
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    REAL NOT NULL,
            is_admin      INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
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

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_user ON research_jobs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
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
    conn.commit()


# --- users ------------------------------------------------------------------


def create_user(username: str, password: str, is_admin: bool = False) -> Dict[str, Any]:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at, is_admin) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), time.time(), 1 if is_admin else 0),
        )
        conn.commit()
        uid = cur.lastrowid
    return {"id": uid, "username": username, "is_admin": is_admin}


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cur.fetchone()


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


def create_session(user_id: int, ttl_seconds: int) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + ttl_seconds),
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
    return get_user_by_id(row["user_id"])


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


# --- research jobs ----------------------------------------------------------


def create_job(
    user_id: int, target: str, question: str,
    credits_cost: int = 0, charged_credits: int = 0,
) -> int:
    """Persist a new research job.

    ``credits_cost``   — the run's list price in points (for the record).
    ``charged_credits``— points actually deducted (0 when a free-quota run);
                         this is what a refund gives back on our-side failure.
    """
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO research_jobs (user_id, target, question, status, created_at, "
            "credits_cost, charged_credits) VALUES (?, ?, ?, 'pending', ?, ?, ?)",
            (user_id, target, question, time.time(), credits_cost, charged_credits),
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


def list_users_with_balance(limit: int = 500) -> List[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT u.id, u.username, u.is_admin, u.created_at, "
        "COALESCE(a.balance, 0) AS balance, "
        "COALESCE(a.total_topup, 0) AS total_topup, "
        "COALESCE(a.total_spent, 0) AS total_spent "
        "FROM users u LEFT JOIN credit_accounts a ON a.user_id = u.id "
        "ORDER BY u.id LIMIT ?",
        (limit,),
    ).fetchall()


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
    }

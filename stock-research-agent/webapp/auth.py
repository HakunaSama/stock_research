"""Authentication: registration, login, logout, and route guards.

Session model — server-side, cookie-based:

* On login/register we mint an opaque token, store it in the ``sessions`` table
  with a TTL, and set it as an **HTTP-only** cookie (``stock_session``). The
  browser can't read it from JS, which blunts XSS token theft.
* Every protected request re-validates the token against the DB, so sessions
  are revocable (logout deletes the row; expiry is enforced server-side).
* Cookie ``Secure`` flag is driven by ``COOKIE_SECURE`` env — off for the
  current public-IP-over-HTTP deploy, flip on the day HTTPS lands.

Registration is open (anyone may sign up) but rate-limited by input validation:
unique username, minimum password length. The very first account created is
promoted to admin automatically.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from . import billing, db


COOKIE_NAME = "stock_session"
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 7 * 24 * 3600))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") in ("1", "true", "True")

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_MIN_PASSWORD_LEN = 6

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- request/response models ------------------------------------------------


class Credentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)


class PublicUser(BaseModel):
    id: int
    username: str
    is_admin: bool


# --- cookie helpers ---------------------------------------------------------


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


# --- dependency: current user ----------------------------------------------


def current_user(stock_session: Optional[str] = Cookie(default=None)):
    """FastAPI dependency — resolve the logged-in user or 401."""
    user = db.get_session_user(stock_session or "")
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user


def optional_user(stock_session: Optional[str] = Cookie(default=None)):
    """Like ``current_user`` but returns None instead of raising."""
    return db.get_session_user(stock_session or "")


# --- routes -----------------------------------------------------------------


@router.post("/register", response_model=PublicUser)
def register(creds: Credentials, response: Response):
    username = creds.username.strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="用户名只能包含字母/数字/_.- 且长度 3-32")
    if len(creds.password) < _MIN_PASSWORD_LEN:
        raise HTTPException(status_code=400, detail=f"密码至少 {_MIN_PASSWORD_LEN} 位")
    if db.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="用户名已被占用")

    # First-ever account becomes admin.
    is_admin = db.count_users() == 0
    user = db.create_user(username, creds.password, is_admin=is_admin)
    db.ensure_account(user["id"])
    billing.grant_signup_bonus(user["id"])
    token = db.create_session(user["id"], SESSION_TTL_SECONDS)
    _set_session_cookie(response, token)
    return PublicUser(id=user["id"], username=username, is_admin=is_admin)


@router.post("/login", response_model=PublicUser)
def login(creds: Credentials, response: Response):
    user = db.get_user_by_username(creds.username.strip())
    if user is None or not db.verify_password(creds.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = db.create_session(user["id"], SESSION_TTL_SECONDS)
    _set_session_cookie(response, token)
    return PublicUser(id=user["id"], username=user["username"], is_admin=bool(user["is_admin"]))


@router.post("/logout")
def logout(response: Response, stock_session: Optional[str] = Cookie(default=None)):
    if stock_session:
        db.delete_session(stock_session)
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=PublicUser)
def me(user=Depends(current_user)):
    return PublicUser(id=user["id"], username=user["username"], is_admin=bool(user["is_admin"]))

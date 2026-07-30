"""Authentication: email registration, login, password recovery, route guards.

Session model — server-side, cookie-based:

* On login/register we mint an opaque token, store it in the ``sessions`` table
  with a TTL, and set it as an **HTTP-only** cookie (``stock_session``). The
  browser can't read it from JS, which blunts XSS token theft.
* Every protected request re-validates the token against the DB, so sessions
  are revocable (logout deletes the row; expiry is enforced server-side;
  disabling an account kills its sessions instantly).
* Cookie ``Secure`` flag is driven by ``COOKIE_SECURE`` env — off for the
  current public-IP-over-HTTP deploy, flip on the day HTTPS lands.

Account model — email-first:

* Registration requires an email + a 6-digit verification code delivered to
  that inbox (see ``emailer.py``; without SMTP config the code is surfaced in
  the response as ``dev_code`` for local testing).
* Login accepts email OR username. Legacy username-only accounts keep working
  and can bind an email later (``/bind-email``).
* Password recovery = email + code + new password; it revokes every session.
* Verification codes: hashed at rest, 10-min TTL, single-use, 5 wrong attempts
  burn the code, 60 s resend cooldown and a daily per-email send cap.

The very first account created is promoted to admin automatically.
"""

from __future__ import annotations

import os
import re
import secrets
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from . import billing, db, emailer


COOKIE_NAME = "stock_session"
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 7 * 24 * 3600))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") in ("1", "true", "True")

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_MIN_PASSWORD_LEN = 6

CODE_TTL_SECONDS = 10 * 60
CODE_RESEND_INTERVAL = 60          # per email+purpose cooldown
CODE_DAILY_LIMIT = 15              # per email, all purposes combined

_PURPOSES = ("register", "reset", "bind")

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- request/response models ------------------------------------------------


class PublicUser(BaseModel):
    id: int
    username: str
    email: str
    email_verified: bool
    is_admin: bool


class SendCodeBody(BaseModel):
    email: str = Field(..., max_length=254)
    purpose: str = Field(...)


class RegisterBody(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., min_length=4, max_length=8)
    password: str = Field(..., min_length=1, max_length=128)
    username: str = Field(default="", max_length=32)


class LoginBody(BaseModel):
    account: str = Field(..., min_length=1, max_length=254)  # email or username
    password: str = Field(..., min_length=1, max_length=128)


class ResetBody(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., min_length=4, max_length=8)
    new_password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordBody(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class BindEmailBody(BaseModel):
    email: str = Field(..., max_length=254)
    code: str = Field(..., min_length=4, max_length=8)


# --- helpers ------------------------------------------------------------------


def _public(user) -> PublicUser:
    return PublicUser(
        id=user["id"],
        username=user["username"],
        email=user["email"] or "",
        email_verified=bool(user["email_verified"]),
        is_admin=bool(user["is_admin"]),
    )


def _norm_email(raw: str) -> str:
    email = raw.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    return email


def _check_password_strength(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        raise HTTPException(status_code=400, detail=f"密码至少 {_MIN_PASSWORD_LEN} 位")


def _derive_username(email: str, wanted: str = "") -> str:
    """Pick a unique username: the requested one, else derived from the email
    local part (sanitized, uniquified with a numeric suffix)."""
    if wanted:
        if not _USERNAME_RE.match(wanted):
            raise HTTPException(status_code=400, detail="用户名只能包含字母/数字/_.- 且长度 3-32")
        if db.get_user_by_username(wanted) is not None:
            raise HTTPException(status_code=409, detail="用户名已被占用")
        return wanted
    base = re.sub(r"[^A-Za-z0-9_.-]", "", email.split("@", 1)[0])[:24] or "user"
    if len(base) < 3:
        base = (base + "user")[:24]
    candidate = base
    while db.get_user_by_username(candidate) is not None:
        candidate = f"{base}{secrets.randbelow(10000)}"
    return candidate


def _issue_session(response: Response, user_id: int) -> None:
    token = db.create_session(user_id, SESSION_TTL_SECONDS)
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


# --- verification codes -------------------------------------------------------


@router.post("/send-code")
def send_code(body: SendCodeBody):
    email = _norm_email(body.email)
    purpose = body.purpose.strip()
    if purpose not in _PURPOSES:
        raise HTTPException(status_code=400, detail="未知的验证码用途")

    existing = db.get_user_by_email(email)
    if purpose in ("register", "bind") and existing is not None:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    if purpose == "reset":
        if existing is None:
            raise HTTPException(status_code=404, detail="该邮箱未注册")
        if existing["disabled"]:
            raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    cooldown = db.seconds_until_resend(email, purpose, CODE_RESEND_INTERVAL)
    if cooldown > 0:
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {cooldown} 秒后再试")
    if db.count_email_codes_today(email) >= CODE_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="今日发送次数已达上限，请明天再试")

    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        dev_code = emailer.send_code(email, purpose, code, CODE_TTL_SECONDS // 60)
    except emailer.EmailError as e:
        raise HTTPException(status_code=502, detail=str(e))
    db.create_email_code(email, purpose, code, CODE_TTL_SECONDS)

    resp = {"ok": True, "ttl_seconds": CODE_TTL_SECONDS, "resend_after": CODE_RESEND_INTERVAL}
    if dev_code is not None:
        # SMTP not configured — surface the code so local dev keeps flowing.
        resp["dev_code"] = dev_code
    return resp


# --- register / login / logout ------------------------------------------------


@router.post("/register", response_model=PublicUser)
def register(body: RegisterBody, response: Response):
    email = _norm_email(body.email)
    _check_password_strength(body.password)
    if db.get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    if not db.verify_email_code(email, "register", body.code.strip()):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    username = _derive_username(email, body.username.strip())
    is_admin = db.count_users() == 0  # first-ever account becomes admin
    user = db.create_user(username, body.password, is_admin=is_admin,
                          email=email, email_verified=True)
    db.ensure_account(user["id"])
    billing.grant_signup_bonus(user["id"])
    _issue_session(response, user["id"])
    return PublicUser(id=user["id"], username=username, email=email,
                      email_verified=True, is_admin=is_admin)


@router.post("/login", response_model=PublicUser)
def login(body: LoginBody, response: Response):
    account = body.account.strip()
    user = None
    if "@" in account:
        user = db.get_user_by_email(account.lower())
    if user is None:
        user = db.get_user_by_username(account)
    if user is None or not db.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user["disabled"]:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    _issue_session(response, user["id"])
    return _public(user)


@router.post("/logout")
def logout(response: Response, stock_session: Optional[str] = Cookie(default=None)):
    if stock_session:
        db.delete_session(stock_session)
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=PublicUser)
def me(user=Depends(current_user)):
    return _public(user)


# --- password recovery / change ------------------------------------------------


@router.post("/reset-password")
def reset_password(body: ResetBody):
    email = _norm_email(body.email)
    _check_password_strength(body.new_password)
    user = db.get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=404, detail="该邮箱未注册")
    if not db.verify_email_code(email, "reset", body.code.strip()):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    db.set_user_password(user["id"], body.new_password)
    db.revoke_user_sessions(user["id"])  # force re-login everywhere
    return {"ok": True}


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    user=Depends(current_user),
    stock_session: Optional[str] = Cookie(default=None),
):
    _check_password_strength(body.new_password)
    if not db.verify_password(body.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")
    db.set_user_password(user["id"], body.new_password)
    # Keep the current session alive; kill the rest.
    db.revoke_user_sessions(user["id"], keep_token=stock_session or "")
    return {"ok": True}


@router.post("/bind-email", response_model=PublicUser)
def bind_email(body: BindEmailBody, user=Depends(current_user)):
    """Legacy (username-only) accounts attach a verified email here; also
    serves as a re-bind path when the user changes mailbox."""
    email = _norm_email(body.email)
    if db.get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="该邮箱已被其他账号绑定")
    if not db.verify_email_code(email, "bind", body.code.strip()):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    db.set_user_email(user["id"], email, verified=True)
    return _public(db.get_user_by_id(user["id"]))

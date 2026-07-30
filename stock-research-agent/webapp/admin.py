"""Admin management API — everything under ``/api/admin`` requires an admin.

Access control reuses the existing ``users.is_admin`` flag (the first-ever
registered account is promoted to admin in ``auth.register``). A single
``require_admin`` dependency guards the whole router: non-admins get 403,
anonymous requests get 401 (from ``auth.current_user`` underneath).

Endpoints (typical "management backend" surface):

    GET  /api/admin/stats                 -> dashboard overview counters
    GET  /api/admin/users                 -> user list + balances
    POST /api/admin/users/{id}/credits    -> manual top-up / adjust points
    POST /api/admin/users/{id}/admin      -> grant/revoke admin
    GET  /api/admin/orders                -> all top-up orders (optional ?status=)
    GET  /api/admin/ledger                -> global credit ledger (audit trail)

Kept intentionally in-process (same FastAPI app) — a separate admin service is
overkill for a single lightweight server.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from . import auth, db

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(user=Depends(auth.current_user)):
    """Dependency: pass through only for admin users, else 403."""
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# --- dashboard --------------------------------------------------------------


@router.get("/stats")
def stats(_admin=Depends(require_admin)):
    return db.admin_stats()


# --- users ------------------------------------------------------------------


def _user_public(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"] or "",
        "email_verified": bool(row["email_verified"]),
        "disabled": bool(row["disabled"]),
        "is_admin": bool(row["is_admin"]),
        "created_at": row["created_at"],
        "balance": row["balance"],
        "total_topup": row["total_topup"],
        "total_spent": row["total_spent"],
        "sub_expires_at": row["sub_expires_at"],
    }


@router.get("/users")
def list_users(
    q: Optional[str] = Query(default=None, max_length=64),
    _admin=Depends(require_admin),
):
    """User list with balances; ``?q=`` fuzzy-matches username or email."""
    return [_user_public(r) for r in db.list_users_with_balance(q=(q or "").strip())]


class CreditAdjust(BaseModel):
    delta: int = Field(..., description="正数充值 / 负数扣减")
    memo: str = Field(default="", max_length=200)


@router.post("/users/{user_id}/credits")
def adjust_user_credits(user_id: int, body: CreditAdjust, admin=Depends(require_admin)):
    """Manually add or deduct a user's points (writes an audit ledger row)."""
    if db.get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.delta == 0:
        raise HTTPException(status_code=400, detail="调整数量不能为 0")
    memo = body.memo or f"管理员({admin['username']})手动调整"
    new_balance = db.adjust_credits(user_id, body.delta, memo)
    if new_balance is None:
        raise HTTPException(status_code=400, detail="扣减数量超过用户当前余额")
    return {"user_id": user_id, "balance": new_balance}


class AdminFlag(BaseModel):
    is_admin: bool


@router.post("/users/{user_id}/admin")
def set_admin(user_id: int, body: AdminFlag, admin=Depends(require_admin)):
    """Grant or revoke a user's admin role."""
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == admin["id"] and not body.is_admin:
        raise HTTPException(status_code=400, detail="不能撤销自己的管理员权限")
    db.set_user_admin(user_id, body.is_admin)
    return {"user_id": user_id, "is_admin": body.is_admin}


class DisabledFlag(BaseModel):
    disabled: bool


@router.post("/users/{user_id}/disabled")
def set_disabled(user_id: int, body: DisabledFlag, admin=Depends(require_admin)):
    """Ban / unban an account. Banning also revokes all live sessions."""
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == admin["id"] and body.disabled:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")
    db.set_user_disabled(user_id, body.disabled)
    return {"user_id": user_id, "disabled": body.disabled}


class MembershipGrant(BaseModel):
    days: int = Field(..., ge=1, le=3650, description="赠送的会员天数")
    memo: str = Field(default="", max_length=200)


@router.post("/users/{user_id}/membership")
def grant_membership(user_id: int, body: MembershipGrant, admin=Depends(require_admin)):
    """Manually gift membership days (e.g. redeeming an off-platform 打赏)."""
    if db.get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    expires_at = db.extend_subscription(user_id, "admin_grant", body.days)
    return {"user_id": user_id, "sub_expires_at": expires_at, "days_added": body.days}


# --- orders & ledger --------------------------------------------------------


@router.get("/orders")
def list_orders(
    status: Optional[str] = Query(default=None),
    _admin=Depends(require_admin),
):
    return [dict(r) for r in db.list_all_orders(status=status)]


@router.get("/ledger")
def list_ledger(_admin=Depends(require_admin)):
    return [dict(r) for r in db.list_all_ledger()]

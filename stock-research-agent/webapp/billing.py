"""Billing: credit plans, research pricing, and a pluggable payment gateway.

The money model is **prepaid points (credits)**:

* Each deep-research run costs ``RESEARCH_CREDIT_COST`` points. Points are
  deducted only after a per-user **free daily quota** is used up (see jobs.py),
  so every account still gets a taste, and paid points cover the LLM bill.
* Users buy points via a *plan* — either a one-off pack or a "monthly card"
  (``kind="monthly"``) that is packaged as a subscription but, under the hood,
  simply grants a batch of points. (True auto-recurring billing needs a real
  gateway's subscription API; until then a monthly card is a larger one-off
  grant — honest and simple.)

Payments go through a small ``PaymentProvider`` seam so the real channel can be
swapped in later (虎皮椒 / 支付宝当面付 / 微信商户) without touching routes or
the DB. Today the only implementation is :class:`StubProvider`, an explicit
placeholder that lets you exercise the whole purchase → credit flow with no
real money — the admin can also top up accounts manually.

Consistency guarantees live in ``db.py``:
* ``db.mark_order_paid`` settles an order and credits points in one
  transaction, guarded by a ``status='pending'`` compare-and-swap, so a
  duplicated/replayed payment callback never double-credits.
"""

from __future__ import annotations

import abc
import os
import secrets
import time
from typing import Dict, List, Optional

from . import db


# --- research pricing -------------------------------------------------------

# Points burned per deep-research run. Tune to your real token cost × margin.
RESEARCH_CREDIT_COST = int(os.environ.get("RESEARCH_CREDIT_COST", 1))
# Points gifted to a brand-new account (0 = none; keep low to deter abuse).
SIGNUP_BONUS_CREDITS = int(os.environ.get("SIGNUP_BONUS_CREDITS", 0))


def research_cost() -> int:
    return max(0, RESEARCH_CREDIT_COST)


# --- plans (credit packs + monthly cards) -----------------------------------
#
# Prices are in cents to avoid float rounding. ``credits`` is how many research
# points the purchase grants. Edit freely — this is your price list.

PLANS: List[Dict] = [
    {"code": "pack_10",  "name": "体验包",   "kind": "pack",    "credits": 10,  "amount_cents": 990,   "desc": "10 次深度研究"},
    {"code": "pack_50",  "name": "标准包",   "kind": "pack",    "credits": 50,  "amount_cents": 3900,  "desc": "50 次深度研究（约 8 折）"},
    {"code": "pack_200", "name": "超值包",   "kind": "pack",    "credits": 200, "amount_cents": 12900, "desc": "200 次深度研究（约 65 折）"},
    {"code": "month",    "name": "月卡",     "kind": "monthly", "credits": 100, "amount_cents": 6800,  "desc": "一次到账 100 点，适合高频使用"},
]

_PLAN_BY_CODE = {p["code"]: p for p in PLANS}


def list_plans() -> List[Dict]:
    return [dict(p) for p in PLANS]


def get_plan(code: str) -> Optional[Dict]:
    p = _PLAN_BY_CODE.get(code)
    return dict(p) if p else None


# --- payment provider seam --------------------------------------------------


class PaymentError(RuntimeError):
    pass


class PaymentProvider(abc.ABC):
    """Swap-in point for a real gateway. Implementations translate our order
    into a payment intent and verify asynchronous callbacks."""

    name: str = "base"

    @abc.abstractmethod
    def create_payment(self, order: "db.sqlite3.Row") -> Dict:
        """Return payment instructions for the client, e.g.::

            {"provider": "...", "out_trade_no": "...",
             "pay_url": "...", "qr_url": "...", "auto_confirm": bool}

        ``auto_confirm`` tells the frontend this is a placeholder gateway that
        can be settled via the simulate endpoint (no real money)."""

    @abc.abstractmethod
    def verify_callback(self, payload: Dict) -> tuple[str, str, bool]:
        """Parse+verify an async payment callback. Returns
        ``(out_trade_no, channel_txid, verified)``."""


class StubProvider(PaymentProvider):
    """Placeholder gateway — NO real payment.

    ``create_payment`` just echoes the order and flags ``auto_confirm`` so the
    UI can offer a "模拟支付(占位)" button that hits the simulate endpoint.
    Replace this class with a real provider (虎皮椒/当面付) when ready.
    """

    name = "stub"

    def create_payment(self, order) -> Dict:
        return {
            "provider": self.name,
            "out_trade_no": order["out_trade_no"],
            "amount_cents": order["amount_cents"],
            "credits": order["credits"],
            "pay_url": "",       # a real provider would return a cashier URL
            "qr_url": "",        # or a QR code to scan
            "auto_confirm": True,
        }

    def verify_callback(self, payload: Dict) -> tuple[str, str, bool]:
        # No signature to verify for the stub; trust the out_trade_no.
        out_trade_no = str(payload.get("out_trade_no", ""))
        txid = str(payload.get("txid", "stub-" + secrets.token_hex(4)))
        return out_trade_no, txid, bool(out_trade_no)


_PROVIDERS = {"stub": StubProvider}


def get_provider() -> PaymentProvider:
    """Return the configured provider (``PAYMENT_PROVIDER`` env, default stub)."""
    name = os.environ.get("PAYMENT_PROVIDER", "stub").strip().lower()
    cls = _PROVIDERS.get(name, StubProvider)
    return cls()


def provider_name() -> str:
    return os.environ.get("PAYMENT_PROVIDER", "stub").strip().lower()


# --- order orchestration ----------------------------------------------------


def _new_trade_no(user_id: int) -> str:
    return f"S{int(time.time())}{user_id}{secrets.token_hex(3)}"


def create_topup_order(user_id: int, plan_code: str) -> Dict:
    """Create a pending order for a plan and return client payment instructions."""
    plan = get_plan(plan_code)
    if plan is None:
        raise PaymentError("套餐不存在")
    provider = get_provider()
    out_trade_no = _new_trade_no(user_id)
    db.create_order(
        out_trade_no=out_trade_no,
        user_id=user_id,
        plan_code=plan["code"],
        credits=plan["credits"],
        amount_cents=plan["amount_cents"],
        channel=provider.name,
    )
    order = db.get_order(out_trade_no)
    pay = provider.create_payment(order)
    pay["plan"] = plan
    pay["status"] = "pending"
    return pay


def settle_order(out_trade_no: str, channel_txid: str = "") -> Optional[Dict]:
    """Mark an order paid and credit points (idempotent). Returns the order dict
    on the paid transition, or None if already settled / unknown."""
    row = db.mark_order_paid(out_trade_no, channel_txid)
    if row is None:
        return None
    return dict(row)


def grant_signup_bonus(user_id: int) -> None:
    if SIGNUP_BONUS_CREDITS > 0:
        db.add_credits(user_id, SIGNUP_BONUS_CREDITS, "signup_bonus", "manual", "", "注册赠送")

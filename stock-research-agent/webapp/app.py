"""FastAPI application — the production web backend.

Replaces the stdlib ``serve.py`` bridge with a framework that can carry auth,
sessions, and a background job queue, while reusing ``serve.py``'s proven
run-scanning helpers verbatim (single source of truth for reading artifacts).

Endpoints
---------
Public:
    GET  /healthz
    GET  /api/config                     -> feature flags (e.g. research_enabled)
    POST /api/auth/register | login | logout   (see webapp.auth)
    GET  /api/auth/me
Authenticated (require a valid session cookie):
    GET  /api/runs
    GET  /api/research/<target>
    GET  /api/kline/<target>
    GET  /api/context/<target>
    POST /api/research/start             -> enqueue an ODR run
    GET  /api/research/jobs              -> this user's job history

CORS is same-origin in production (nginx serves the SPA and reverse-proxies
``/api`` to this app), so no wildcard is needed. Set ``DEV_CORS_ORIGIN`` to open
it up for local ``vite dev`` against a separately-running backend.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reuse serve.py's artifact readers (stdlib-only, already battle-tested).
from serve import _load_kline, _run_summary, _scan_runs

from . import admin, auth, billing, db, jobs

WORKDIR = os.environ.get("STOCK_DATA_DIR", "/tmp/stock-terminal-data")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: init DB schema, drop stale sessions, spin up the research worker
    # pool (which also re-queues jobs left pending by a previous crash).
    db.get_conn()
    db.purge_expired_sessions()
    jobs.start_workers()
    yield


app = FastAPI(title="Stock Research Terminal", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)

# Same-origin in prod; opt-in CORS for local dev (vite on :5173 → backend :8000).
_dev_origin = os.environ.get("DEV_CORS_ORIGIN")
if _dev_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _dev_origin.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# --- public -----------------------------------------------------------------


@app.get("/healthz")
def healthz():
    runs = _scan_runs(WORKDIR)
    return {"ok": True, "targets": sorted(runs.keys())}


@app.get("/api/config")
def config():
    """Feature flags the SPA reads once at boot."""
    return {
        "research_enabled": jobs.research_available(),
        "daily_quota": jobs.RESEARCH_DAILY_QUOTA,
        "research_cost": billing.research_cost(),
        "payment_provider": billing.provider_name(),
    }


# --- read-only run data (authenticated) -------------------------------------


@app.get("/api/runs")
def api_runs(_user=Depends(auth.current_user)):
    runs = _scan_runs(WORKDIR)
    return [_run_summary(c) for c in runs.values()]


def _require_run(target: str):
    ctx = _scan_runs(WORKDIR).get(target)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"没有 {target} 的研究记录")
    return ctx


# --- research jobs (authenticated) ------------------------------------------
# NOTE: these concrete paths MUST be declared before the dynamic
# ``/api/research/{target}`` route below, or FastAPI would match "jobs"/"start"
# as a target. Route matching is registration-order sensitive.


class StartResearch(BaseModel):
    target: str = Field(..., min_length=1, max_length=32)
    question: str = Field(default="", max_length=200)


def _job_public(row) -> dict:
    return {
        "id": row["id"],
        "target": row["target"],
        "question": row["question"],
        "status": row["status"],
        "run_id": row["run_id"],
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


@app.post("/api/research/start")
def start_research(body: StartResearch, user=Depends(auth.current_user)):
    try:
        job_id = jobs.enqueue(user["id"], body.target, body.question)
    except jobs.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except jobs.InsufficientCredits as e:
        # 402 Payment Required — out of free quota and not enough points.
        raise HTTPException(status_code=402, detail=str(e))
    except jobs.ResearchUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return _job_public(db.get_job(job_id))


@app.get("/api/research/jobs")
def list_jobs(user=Depends(auth.current_user)):
    return [_job_public(r) for r in db.list_jobs_for_user(user["id"])]


# --- wallet / billing (authenticated) ---------------------------------------


def _free_left(user_id: int) -> int:
    used = db.count_free_jobs_since(user_id, jobs._day_start_ts())  # noqa: SLF001
    return max(0, jobs.RESEARCH_DAILY_QUOTA - used)


@app.get("/api/wallet")
def wallet(user=Depends(auth.current_user)):
    """The current user's balance + today's remaining free runs."""
    acct = db.get_account(user["id"])
    return {
        **acct,
        "free_left": _free_left(user["id"]),
        "daily_quota": jobs.RESEARCH_DAILY_QUOTA,
        "research_cost": billing.research_cost(),
    }


@app.get("/api/wallet/ledger")
def wallet_ledger(user=Depends(auth.current_user)):
    return [dict(r) for r in db.list_ledger(user["id"])]


@app.get("/api/plans")
def plans(_user=Depends(auth.current_user)):
    return {"plans": billing.list_plans(), "provider": billing.provider_name()}


class BuyBody(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=40)


@app.post("/api/orders")
def create_order(body: BuyBody, user=Depends(auth.current_user)):
    """Create a top-up order and return payment instructions.

    With the stub provider ``auto_confirm`` is True, so the SPA can settle the
    order via /api/orders/{out_trade_no}/simulate (placeholder, no real money).
    """
    try:
        pay = billing.create_topup_order(user["id"], body.plan_code)
    except billing.PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return pay


@app.get("/api/orders")
def list_orders(user=Depends(auth.current_user)):
    return [dict(r) for r in db.list_orders_for_user(user["id"])]


@app.get("/api/orders/{out_trade_no}")
def get_order(out_trade_no: str, user=Depends(auth.current_user)):
    row = db.get_order(out_trade_no)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="订单不存在")
    return dict(row)


@app.post("/api/orders/{out_trade_no}/simulate")
def simulate_payment(out_trade_no: str, user=Depends(auth.current_user)):
    """Placeholder-gateway settlement — only valid while the stub provider is
    active. Lets you exercise the purchase→credit flow with no real payment.
    A real provider settles via its async callback instead (see /api/pay/notify).
    """
    if billing.provider_name() != "stub":
        raise HTTPException(status_code=400, detail="真实支付渠道不支持模拟支付")
    row = db.get_order(out_trade_no)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="订单不存在")
    settled = billing.settle_order(out_trade_no, channel_txid="stub-simulated")
    return {
        "ok": settled is not None,
        "balance": db.get_balance(user["id"]),
        "order": dict(db.get_order(out_trade_no)),
    }


# --- read-only run data (authenticated, dynamic target) ---------------------


@app.get("/api/research/{target}")
def api_research(target: str, _user=Depends(auth.current_user)):
    ctx = _require_run(target)
    slot = ctx.get("research") or {}
    return {"target": target, "run_id": ctx.get("run_id", ""), **slot}


@app.get("/api/kline/{target}")
def api_kline(target: str, _user=Depends(auth.current_user)):
    ctx = _require_run(target)
    payload = _load_kline(WORKDIR, ctx)
    return {"target": target, "run_id": ctx.get("run_id", ""), **payload}


@app.get("/api/context/{target}")
def api_context(target: str, _user=Depends(auth.current_user)):
    return _require_run(target)

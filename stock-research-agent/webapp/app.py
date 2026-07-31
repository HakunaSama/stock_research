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
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reuse serve.py's artifact readers (stdlib-only, already battle-tested).
from serve import _load_kline, _run_summary, _scan_runs

from stock_agent import market
from stock_agent.live_llm import load_dotenv

# Load .env BEFORE importing webapp modules: several of them freeze env vars
# into module constants at import time (billing costs, session TTL, …), and
# emailer/SMTP reads env per send. Explicitly exported vars still win.
load_dotenv()

from . import admin, auth, billing, db, emailer, hall, jobs  # noqa: E402

WORKDIR = os.environ.get("STOCK_DATA_DIR", "/tmp/stock-terminal-data")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: init DB schema, drop stale sessions, spin up the research worker
    # pool (which also re-queues jobs left pending by a previous crash).
    db.get_conn()
    db.purge_expired_sessions()
    jobs.start_workers()
    yield


app = FastAPI(title="知势 Cheese", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(hall.router)

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
        "sub_daily_quota": billing.sub_daily_quota(),
        "research_cost": billing.research_cost(),
        "payment_provider": billing.provider_name(),
        # True => SMTP not configured; send-code responses carry dev_code and
        # the SPA shows a "development mode" hint on email forms.
        "email_dev_mode": not emailer.email_configured(),
    }


# --- live market data (authenticated) ---------------------------------------
# 真实行情：报价/指数/搜索/K线/资讯，全部来自 stock_agent.market（腾讯/东财/
# 新浪多源故障转移 + 进程内 TTL 缓存）。上游整体失败时映射为 502。


def _market_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except market.MarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/quotes")
def api_quotes(symbols: str = "", _user=Depends(auth.current_user)):
    syms = [s for s in symbols.split(",") if s.strip()]
    return _market_call(market.get_quotes, syms)


@app.get("/api/market/indices")
def api_indices(_user=Depends(auth.current_user)):
    return _market_call(market.get_indices)


@app.get("/api/market/search")
def api_search(q: str = "", _user=Depends(auth.current_user)):
    return _market_call(market.search, q)


@app.get("/api/market/rank")
def api_rank(kind: str = "pct_desc", limit: int = 30, _user=Depends(auth.current_user)):
    return _market_call(market.get_rank, kind, limit)


@app.get("/api/market/kline/{symbol}")
def api_live_kline(symbol: str, period: str = "day", count: int = 180,
                   _user=Depends(auth.current_user)):
    return _market_call(market.get_live_kline, symbol, period=period, count=count)


@app.get("/api/news/{code}")
def api_news(code: str, _user=Depends(auth.current_user)):
    return _market_call(market.get_news, code)


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
    # None → 用当前激活策略；0 → 强制内置示例；其余 → 指定自己的策略。
    strategy_id: int | None = Field(default=None, ge=0)


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
        "strategy_id": row["strategy_id"],
        "strategy_name": row["strategy_name"],
    }


@app.post("/api/research/start")
def start_research(body: StartResearch, user=Depends(auth.current_user)):
    try:
        job_id = jobs.enqueue(user["id"], body.target, body.question,
                              strategy_id=body.strategy_id)
    except jobs.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except jobs.InsufficientCredits as e:
        # 402 Payment Required — out of free quota and not enough points.
        raise HTTPException(status_code=402, detail=str(e))
    except jobs.ResearchUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except jobs.StrategyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _job_public(db.get_job(job_id))


@app.get("/api/research/jobs")
def list_jobs(user=Depends(auth.current_user)):
    return [_job_public(r) for r in db.list_jobs_for_user(user["id"])]


# --- strategy library (authenticated) ----------------------------------------
# 策略热插拔:用户维护自己的自然语言策略,激活其一;发起研究时由管线的
# strategy 编译器(stock_agent/strategy.py)编译成结构化规则逐条核对。
# id=0 恒指内置示例策略(不可编辑/删除,作为无自定义策略时的回退)。
# 公开到「策略大厅」后,其他用户可点赞/收藏/评论/采用到自己的库。

MAX_STRATEGIES_PER_USER = 20


class StrategyBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    raw_text: str = Field(..., min_length=10, max_length=4000)
    summary: str = Field(default="", max_length=120)
    tags: List[str] = Field(default_factory=list, max_length=8)
    activate: bool = Field(default=False)


class PublishBody(BaseModel):
    is_public: bool = True
    summary: str = Field(default="", max_length=120)
    tags: Optional[List[str]] = Field(default=None, max_length=8)


def _strategy_public(row) -> dict:
    tags = db.get_strategy_tags(row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "raw_text": row["raw_text"],
        "summary": row["summary"] or "",
        "tags": tags,
        "is_active": bool(row["is_active"]),
        "is_public": bool(row["is_public"]),
        "like_count": int(row["like_count"] or 0),
        "favorite_count": int(row["favorite_count"] or 0),
        "comment_count": int(row["comment_count"] or 0),
        "published_at": row["published_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _merge_tags(explicit: List[str], raw_text: str) -> List[str]:
    """Combine form tags with inline #hashtags from the strategy text."""
    merged = list(explicit or []) + db.extract_hashtags(raw_text)
    return db.normalize_tags(merged)


@app.get("/api/strategies")
def list_strategies(user=Depends(auth.current_user)):
    rows = db.list_strategies(user["id"])
    active = next((r["id"] for r in rows if r["is_active"]), 0)
    return {
        "active_id": active,  # 0 = 内置示例
        "builtin": {
            "id": 0,
            "name": jobs.DEFAULT_STRATEGY_NAME,
            "raw_text": jobs.DEFAULT_STRATEGY_TEXT.strip(),
        },
        "strategies": [_strategy_public(r) for r in rows],
    }


@app.post("/api/strategies")
def create_strategy(body: StrategyBody, user=Depends(auth.current_user)):
    if db.count_strategies(user["id"]) >= MAX_STRATEGIES_PER_USER:
        raise HTTPException(status_code=400, detail=f"策略数量已达上限（{MAX_STRATEGIES_PER_USER} 条）。")
    tags = _merge_tags(body.tags, body.raw_text)
    sid = db.create_strategy(
        user["id"], body.name.strip(), body.raw_text.strip(),
        activate=body.activate, summary=body.summary.strip(), tags=tags,
    )
    return _strategy_public(db.get_strategy(sid, user["id"]))


@app.put("/api/strategies/{sid}")
def update_strategy(sid: int, body: StrategyBody, user=Depends(auth.current_user)):
    tags = _merge_tags(body.tags, body.raw_text)
    if not db.update_strategy(
        sid, user["id"], body.name.strip(), body.raw_text.strip(),
        summary=body.summary.strip(), tags=tags,
    ):
        raise HTTPException(status_code=404, detail="策略不存在")
    if body.activate:
        db.set_active_strategy(user["id"], sid)
    return _strategy_public(db.get_strategy(sid, user["id"]))


@app.delete("/api/strategies/{sid}")
def delete_strategy(sid: int, user=Depends(auth.current_user)):
    if not db.delete_strategy(sid, user["id"]):
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"ok": True}


@app.post("/api/strategies/{sid}/activate")
def activate_strategy(sid: int, user=Depends(auth.current_user)):
    """激活指定策略;sid=0 表示改用内置示例(清除所有激活位)。"""
    if not db.set_active_strategy(user["id"], sid):
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"ok": True, "active_id": sid}


@app.post("/api/strategies/{sid}/publish")
def publish_strategy(sid: int, body: PublishBody, user=Depends(auth.current_user)):
    """发布 / 取消发布到策略大厅。发布时可同步摘要与标签。"""
    row = db.get_strategy(sid, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    tags = body.tags
    if body.is_public and tags is None:
        tags = db.get_strategy_tags(sid) or db.extract_hashtags(row["raw_text"])
    summary = body.summary.strip() if body.summary else (row["summary"] or "")
    if not db.publish_strategy(
        sid, user["id"], body.is_public, tags=tags, summary=summary or None,
    ):
        raise HTTPException(status_code=404, detail="策略不存在")
    return _strategy_public(db.get_strategy(sid, user["id"]))


# --- wallet / billing (authenticated) ---------------------------------------


def _free_left(user_id: int) -> int:
    used = db.count_free_jobs_since(user_id, jobs._day_start_ts())  # noqa: SLF001
    return max(0, jobs.daily_quota_for(user_id) - used)


@app.get("/api/wallet")
def wallet(user=Depends(auth.current_user)):
    """Balance + today's remaining free runs + membership state."""
    acct = db.get_account(user["id"])
    sub = db.get_subscription(user["id"])
    sub_active = bool(sub and sub["expires_at"] > time.time())
    return {
        **acct,
        "free_left": _free_left(user["id"]),
        "daily_quota": jobs.daily_quota_for(user["id"]),
        "research_cost": billing.research_cost(),
        "sub_active": sub_active,
        "sub_expires_at": sub["expires_at"] if sub else None,
        "sub_plan_code": sub["plan_code"] if sub else "",
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

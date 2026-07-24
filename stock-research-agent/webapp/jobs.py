"""Background worker queue for user-initiated ODR research runs.

A real research run drives a slow reasoning LLM through the whole ODR pipeline
(strategy → multi-agent deep research → K-line → analysis) and takes minutes.
So the HTTP handler must NOT run it inline — it enqueues a job and returns
immediately; a small pool of worker threads drains the queue.

Guardrails (research is expensive and abuse-prone):

* **User-initiated only** — nothing auto-runs on login; the frontend must POST.
* **Free daily quota then credits** — each user gets ``RESEARCH_DAILY_QUOTA``
  free runs per day; beyond that a run costs ``billing.research_cost()`` points
  (see billing.py). No free quota left and no points => the run is refused.
* **Bounded concurrency** (``RESEARCH_WORKERS``, default 1) so a lightweight
  server isn't overwhelmed and the LLM bill stays predictable.
* LLM credentials come **only** from the server environment (``build_live_llm``)
  — they are never accepted from or sent to the client.
* **Auto-refund on our-side failure** — if the run fails because of an LLM/infra
  error (not the user's doing), any points charged are refunded (idempotently).

Jobs and their lifecycle (pending → running → done/failed) live in the
``research_jobs`` table so status survives a page refresh and can be polled.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time

from stock_agent import StockConfig, run_pipeline
from stock_agent.live_llm import LiveLLMError, build_live_llm, load_dotenv

from . import billing, db

log = logging.getLogger("webapp.jobs")

# Same demo strategy used by run_live.py — a big-V momentum playbook.
STRATEGY_TEXT = """
张大动量策略：牛市或震荡市里，个股回踩20日均线不破、MACD金叉、
成交量较5日均量放大超过50% 时买入；跌破10日线或MACD死叉卖出；
单笔止损 -8%，单一仓位不超过30%。熊市不适用。
"""

RESEARCH_WORKERS = int(os.environ.get("RESEARCH_WORKERS", 1))
RESEARCH_DAILY_QUOTA = int(os.environ.get("RESEARCH_DAILY_QUOTA", 5))
_DATA_DIR = os.environ.get("STOCK_DATA_DIR", "/tmp/stock-terminal-data")

_job_queue: "queue.Queue[int]" = queue.Queue()
_workers: list[threading.Thread] = []
_started = False
_start_lock = threading.Lock()


class QuotaExceeded(RuntimeError):
    pass


class InsufficientCredits(RuntimeError):
    """Free daily quota exhausted and not enough points to pay for a run."""

    def __init__(self, needed: int, balance: int):
        self.needed = needed
        self.balance = balance
        super().__init__(
            f"今日免费次数已用完，本次研究需要 {needed} 点，当前余额 {balance} 点，请充值后再试。"
        )


class ResearchUnavailable(RuntimeError):
    """No LLM credentials configured on the server — online research is off."""


def research_available() -> bool:
    """True if the server has LLM credentials, so online research can run."""
    load_dotenv()
    try:
        build_live_llm()
        return True
    except LiveLLMError:
        return False


def _build_config() -> StockConfig:
    config = StockConfig()
    config.workdir = _DATA_DIR
    # Keep online runs lean so they finish in a sensible time on a small box.
    config.research.odr.max_supervisor_iterations = 2
    config.research.odr.max_concurrent_units = 2
    config.research.odr.max_researcher_iterations = 3
    config.research.max_attempts = 2
    return config


def _process(job_id: int) -> None:
    row = db.get_job(job_id)
    if row is None:
        return
    db.update_job(job_id, status="running", started_at=time.time())
    try:
        load_dotenv()
        llm = build_live_llm()
        config = _build_config()
        ctx = run_pipeline(
            target=row["target"],
            question=row["question"] or "当前是否是买入时机？",
            horizon="1-3 个月",
            decision_type=None,
            strategy_text=STRATEGY_TEXT,
            strategy_source="bigv:张大",
            llm=llm,
            config=config,
        )
        db.update_job(
            job_id, status="done", run_id=ctx.run_id, finished_at=time.time(), error=""
        )
        log.info("research job %s done -> run_id=%s", job_id, ctx.run_id)
    except LiveLLMError as e:
        db.update_job(job_id, status="failed", error=f"LLM 配置/调用错误: {e}",
                      finished_at=time.time())
        _refund_failed_job(job_id)
        log.warning("research job %s failed (llm): %s", job_id, e)
    except Exception as e:  # noqa: BLE001 — worker must never crash the pool
        db.update_job(job_id, status="failed", error=str(e), finished_at=time.time())
        _refund_failed_job(job_id)
        log.exception("research job %s failed", job_id)


def _refund_failed_job(job_id: int) -> None:
    """Give back any points charged for a run that failed on our side."""
    try:
        refunded = db.refund_job(job_id)
        if refunded:
            log.info("refunded %s point(s) for failed job %s", refunded, job_id)
    except Exception:  # noqa: BLE001 — refund failure must not crash the worker
        log.exception("refund failed for job %s", job_id)


def _worker_loop() -> None:
    while True:
        job_id = _job_queue.get()
        try:
            _process(job_id)
        finally:
            _job_queue.task_done()


def start_workers() -> None:
    """Spin up the worker pool and re-queue jobs left pending by a crash."""
    global _started
    with _start_lock:
        if _started:
            return
        for i in range(max(1, RESEARCH_WORKERS)):
            t = threading.Thread(target=_worker_loop, name=f"research-worker-{i}", daemon=True)
            t.start()
            _workers.append(t)
        # Crash recovery: anything stuck in pending/running gets re-queued.
        for row in db.list_pending_jobs():
            db.update_job(row["id"], status="pending")
            _job_queue.put(row["id"])
        _started = True
        log.info("started %d research worker(s)", len(_workers))


def _day_start_ts() -> float:
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))


def enqueue(user_id: int, target: str, question: str) -> int:
    """Charge for and enqueue a research run.

    Billing order: use a free daily run if any remain, otherwise deduct
    ``billing.research_cost()`` points. If neither is available, refuse.

    Raises:
        ResearchUnavailable — no server LLM credentials.
        InsufficientCredits — out of free quota AND not enough points.
    """
    if not research_available():
        raise ResearchUnavailable("服务器未配置大模型凭据，暂不支持在线发起研究。")

    day = _day_start_ts()
    free_used = db.count_free_jobs_since(user_id, day)
    cost = billing.research_cost()

    if free_used < RESEARCH_DAILY_QUOTA:
        # Covered by today's free allowance — charge nothing.
        job_id = db.create_job(user_id, target.strip(), question.strip(),
                               credits_cost=cost, charged_credits=0)
    else:
        # Free quota gone: try to pay with points. spend_credits is atomic and
        # returns None if the balance can't cover it (nothing deducted).
        if cost <= 0:
            job_id = db.create_job(user_id, target.strip(), question.strip(),
                                   credits_cost=0, charged_credits=0)
        else:
            new_balance = db.spend_credits(
                user_id, cost, "research_spend", "job", "", "发起深度研究"
            )
            if new_balance is None:
                raise InsufficientCredits(cost, db.get_balance(user_id))
            # Record the job with charged_credits so a failure can refund it.
            job_id = db.create_job(user_id, target.strip(), question.strip(),
                                   credits_cost=cost, charged_credits=cost)
            # Re-tag the spend ledger row with the concrete job id for audit.
            _retag_spend_ledger(user_id, job_id)

    _job_queue.put(job_id)
    return job_id


def _retag_spend_ledger(user_id: int, job_id: int) -> None:
    """Point the most recent research_spend ledger row (ref_id='') at the job.

    We spend before the job row exists (to fail fast on insufficient balance),
    so the ledger's ref_id is filled in here for a clean audit trail."""
    try:
        conn = db.get_conn()
        with db._lock:  # noqa: SLF001 — same-module private lock, intentional
            conn.execute(
                "UPDATE credit_ledger SET ref_id = ? WHERE id = ("
                "  SELECT id FROM credit_ledger WHERE user_id = ? AND reason = 'research_spend' "
                "  AND ref_type = 'job' AND ref_id = '' ORDER BY id DESC LIMIT 1)",
                (str(job_id), user_id),
            )
            conn.commit()
    except Exception:  # noqa: BLE001 — audit nicety, never block the run
        log.exception("failed to retag spend ledger for job %s", job_id)

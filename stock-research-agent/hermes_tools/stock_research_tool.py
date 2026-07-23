"""Hermes tool: deep_research.

Runs the DeepResearch judge/retry loop for a run and writes the accepted (or
best-effort) digest into the run's ResearchContext. An independent judge scores
each attempt; below-threshold attempts are retried WITHOUT feedback (independent
re-sampling), up to max_attempts, rotating the retrieval angle and nudging
temperature for diversity.

Producer: by default an ``LLMResearcher`` backed by the hermes model (one-shot,
no live web). To use real web retrieval, inject a delegate-backed researcher
(a ``delegate_task`` subagent with web_search/web_extract) — see the design doc.

Registration follows the hermes pattern (see tools/memory_tool.py).
"""

from __future__ import annotations

import json

from stock_agent.config import StockConfig
from stock_agent.research import run_deep_research, build_researcher


DEEP_RESEARCH_SCHEMA = {
    "name": "deep_research",
    "description": (
        "Collect market research for the run's target and gate it with an "
        "independent judge: accept when score >= threshold, else retry WITHOUT "
        "feedback (independent re-sampling, rotating angle + temperature) up to "
        "max_attempts; if never cleared, keep the best attempt flagged. Writes "
        "the digest into the run's context. Returns JSON: status, score, "
        "attempts, digest, sources, note."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run identifier from stock_run_init.",
            },
        },
        "required": ["run_id"],
    },
}


def _handle(args, **kw):
    from stock_agent.hermes_bridge import HermesLLM, load_stock_config, load_context

    config: StockConfig = load_stock_config()
    ctx = load_context(config, args["run_id"])

    research_llm = HermesLLM(fallback_model=config.research.research_model, task="deep_research")
    judge_llm = HermesLLM(fallback_model=config.research.judge_model, task="deep_research")

    # Prefer REAL web research: give ODR a delegate-backed retriever (a
    # web_search/web_extract subagent). If this hermes build exposes no
    # delegation API we recognize, resolve_delegate() returns None and ODR
    # falls back to the single-LLM stub — same pipeline either way.
    retriever = None
    if config.research.engine == "odr":
        try:
            from hermes_tools.odr_retriever import DelegateRetriever, resolve_delegate

            delegate = resolve_delegate()
            if delegate is not None:
                retriever = DelegateRetriever(
                    delegate=delegate,
                    llm=research_llm,
                    model=config.research.odr.research_model,
                )
        except Exception:  # noqa: BLE001 — never block research on wiring
            retriever = None

    # Engine per config.research.engine: "odr" (multi-agent OpenDeepResearcher)
    # or "legacy" (single-shot). Either way the judge/retry outer loop re-runs
    # the whole producer when the score is too low.
    researcher = build_researcher(research_llm, config, retriever=retriever)

    run_deep_research(ctx, researcher, judge_llm, config)
    return json.dumps(
        {
            "status": ctx.research.status,
            "score": ctx.research.score,
            "attempts": ctx.research.attempts,
            "digest": ctx.research.digest,
            "sources": ctx.research.sources,
            "note": ctx.research.note,
        },
        ensure_ascii=False, indent=2,
    )


try:
    from tools.registry import registry

    registry.register(
        name="deep_research",
        toolset="stock",
        schema=DEEP_RESEARCH_SCHEMA,
        handler=_handle,
        emoji="🔎",
        description="Collect market research with judge scoring + no-feedback retry.",
    )
except ImportError:
    # Running standalone (outside hermes) — registration is a no-op.
    pass
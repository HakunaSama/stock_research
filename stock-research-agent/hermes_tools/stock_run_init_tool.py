"""Hermes tool: stock_run_init.

Creates a fresh ResearchContext for a stock-research run and persists it, so the
subsequent stateful tools (strategy_compile, deep_research, kline_fetch,
analysis_run) can load/mutate/save the same context by run_id.

Registration follows the hermes pattern (see tools/memory_tool.py).
"""

from __future__ import annotations

import json

from stock_agent.context import ResearchContext


STOCK_RUN_INIT_SCHEMA = {
    "name": "stock_run_init",
    "description": (
        "Start a stock-research run: create and persist a ResearchContext. "
        "Returns JSON with the run_id to pass to all subsequent stock tools. "
        "decision_type is optional (stock_pick|timing|sector|portfolio); if "
        "omitted the analysis stage routes it automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Ticker / basket / sector label."},
            "question": {"type": "string", "description": "Free-text research question."},
            "horizon": {"type": "string", "description": "Time horizon, e.g. '1-3 个月'."},
            "decision_type": {
                "type": "string",
                "enum": ["stock_pick", "timing", "sector", "portfolio"],
                "description": "Optional decision scenario; omit to auto-route.",
            },
        },
        "required": ["target"],
    },
}


def _handle(args, **kw):
    from stock_agent.hermes_bridge import load_stock_config

    config = load_stock_config()
    ctx = ResearchContext.new(
        target=args["target"],
        question=args.get("question", ""),
        horizon=args.get("horizon", ""),
        decision_type=args.get("decision_type"),
    )
    ctx.save(config.workdir)
    return json.dumps({"run_id": ctx.run_id, "target": ctx.query.target}, ensure_ascii=False)


try:
    from tools.registry import registry

    registry.register(
        name="stock_run_init",
        toolset="stock",
        schema=STOCK_RUN_INIT_SCHEMA,
        handler=_handle,
        emoji="🚀",
        description="Start a stock-research run and return its run_id.",
    )
except ImportError:
    pass

"""Hermes tool: analysis_run.

Runs the 6-stage analysis pipeline over an existing ResearchContext (loaded from
its run_id) and returns the structured verdict as JSON. The context must already
have strategy / research / kline slots populated by the earlier tools.

Registration follows the hermes pattern (see tools/memory_tool.py):
``registry.register(name, toolset, schema, handler, ...)``.
"""

from __future__ import annotations

import json

from stock_agent.config import StockConfig
from stock_agent.analysis import run_analysis


ANALYSIS_RUN_SCHEMA = {
    "name": "analysis_run",
    "description": (
        "Run the 6-stage analysis pipeline (fundamental -> technical -> "
        "strategy-fit -> synthesis/route -> verdict -> risk&exec) over a run's "
        "ResearchContext and return the structured conclusion. Requires that "
        "strategy_compile, deep_research, and kline_fetch have already populated "
        "the context for this run_id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "The run identifier whose context.json to analyze.",
            },
        },
        "required": ["run_id"],
    },
}


def _handle(args, **kw):
    from stock_agent.hermes_bridge import HermesLLM, load_stock_config, load_context

    config: StockConfig = load_stock_config()
    ctx = load_context(config, args["run_id"])

    llm = HermesLLM(fallback_model=config.analysis.model, task="analysis")
    judge_llm = HermesLLM(fallback_model=config.research.judge_model, task="analysis")
    run_analysis(ctx, llm, judge_llm, config)
    return json.dumps(ctx.analysis, ensure_ascii=False, indent=2)


try:
    from tools.registry import registry

    registry.register(
        name="analysis_run",
        toolset="stock",
        schema=ANALYSIS_RUN_SCHEMA,
        handler=_handle,
        emoji="🧠",
        description="Run the 6-stage analysis pipeline and return the structured verdict.",
    )
except ImportError:
    # Running standalone (outside hermes) — registration is a no-op.
    pass

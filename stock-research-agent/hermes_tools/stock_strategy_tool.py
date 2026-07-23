"""Hermes tool: strategy_compile.

Compiles a raw trading strategy (inline text or a local strategy.md) into a
strict schema + an LLM-friendly prompt block, writes it into the run's
ResearchContext, and returns it as JSON.

Registration follows the hermes pattern (see tools/memory_tool.py):
``registry.register(name, toolset, schema, handler, ...)``.
"""

from __future__ import annotations

import json

from stock_agent.config import StockConfig
from stock_agent.strategy import compile_strategy


STRATEGY_COMPILE_SCHEMA = {
    "name": "strategy_compile",
    "description": (
        "Compile a raw trading strategy (from the user or a market influencer) "
        "into a strict, unambiguous schema plus a prompt block the analysis "
        "stages can check rule-by-rule, and write it into the run's context. "
        "Provide EITHER 'raw_text' (inline strategy) OR 'strategy_path' (a local "
        "strategy.md file). Returns JSON with keys: schema, compiled_prompt, "
        "checks. No URL/Git fetch — local files only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run identifier from stock_run_init.",
            },
            "raw_text": {
                "type": "string",
                "description": "Inline raw strategy text.",
            },
            "strategy_path": {
                "type": "string",
                "description": "Path to a local strategy.md file.",
            },
            "source": {
                "type": "string",
                "description": "Provenance tag, e.g. 'user' or 'bigv:<name>'.",
            },
        },
        "required": ["run_id"],
    },
}


def _handle(args, **kw):
    from stock_agent.hermes_bridge import HermesLLM, load_stock_config, load_context

    config: StockConfig = load_stock_config()
    ctx = load_context(config, args["run_id"])
    llm = HermesLLM(fallback_model=config.strategy.compile_model, task="skills_hub")
    compile_strategy(
        ctx, llm,
        raw_text=args.get("raw_text"),
        strategy_path=args.get("strategy_path"),
        source=args.get("source", "user"),
        config=config,
    )
    ctx.save(config.workdir)
    return json.dumps(
        {
            "schema": ctx.strategy.schema,
            "compiled_prompt": ctx.strategy.compiled_prompt,
            "checks": ctx.strategy.checks,
            "source": ctx.strategy.source,
        },
        ensure_ascii=False, indent=2,
    )


try:
    from tools.registry import registry

    registry.register(
        name="strategy_compile",
        toolset="stock",
        schema=STRATEGY_COMPILE_SCHEMA,
        handler=_handle,
        emoji="📐",
        description="Compile a raw trading strategy into a checkable schema + prompt block.",
    )
except ImportError:
    # Running standalone (outside hermes) — registration is a no-op.
    pass

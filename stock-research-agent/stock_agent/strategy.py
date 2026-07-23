"""Module 1: Strategy hot-plug — compiler.

Users (or market influencers) drop a raw strategy as free text or a
``strategy.md`` file. Raw strategies are vague and heterogeneous, so we compile
them into a strict schema (entry/exit/risk rules + explicit assumptions) and
render that into a prompt block the analysis stages can check rule-by-rule.

Standalone entry point: ``compile_strategy(...)``.
Hermes tool wrapper: see ``hermes_tools/stock_strategy_tool.py``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .config import StockConfig, DEFAULT_CONFIG
from .context import ResearchContext, StrategySlot
from .llm import LLMClient, extract_json
from .templates import render


_REQUIRED_KEYS = (
    "name", "thesis", "entry_rules", "exit_rules", "risk_rules",
    "indicators", "timeframe", "assumptions", "ambiguities",
)


def _normalize_schema(raw: Any) -> Dict[str, Any]:
    """Coerce the LLM output into the fixed schema, filling missing keys."""
    data = raw if isinstance(raw, dict) else {}
    schema: Dict[str, Any] = {}
    list_keys = {
        "entry_rules", "exit_rules", "risk_rules",
        "indicators", "assumptions", "ambiguities",
    }
    for key in _REQUIRED_KEYS:
        if key in list_keys:
            val = data.get(key, [])
            if isinstance(val, str):
                val = [val] if val.strip() else []
            schema[key] = [str(x) for x in val] if isinstance(val, list) else []
        else:
            schema[key] = str(data.get(key, "") or "")
    return schema


def render_compiled_prompt(schema: Dict[str, Any]) -> str:
    """Render the structured schema into an LLM-friendly prompt block."""
    def bullet(items):
        return "\n".join(f"  - {x}" for x in items) if items else "  - (无)"

    lines = [
        f"## 交易策略：{schema.get('name') or '未命名'}",
        f"核心思路：{schema.get('thesis') or '(未给出)'}",
        f"周期：{schema.get('timeframe') or '(未指定)'}",
        f"涉及指标：{', '.join(schema.get('indicators') or []) or '(无)'}",
        "",
        "买入条件（entry，需逐条核对）：",
        bullet(schema.get("entry_rules")),
        "",
        "卖出条件（exit）：",
        bullet(schema.get("exit_rules")),
        "",
        "风险/仓位规则（risk）：",
        bullet(schema.get("risk_rules")),
    ]
    assumptions = schema.get("assumptions") or []
    ambiguities = schema.get("ambiguities") or []
    if assumptions:
        lines += ["", "编译时的假设：", bullet(assumptions)]
    if ambiguities:
        lines += ["", "原文模糊点（已按假设处理，结论中需提示）：", bullet(ambiguities)]
    return "\n".join(lines)


def _collect_checks(schema: Dict[str, Any]) -> list:
    checks = []
    checks += list(schema.get("entry_rules") or [])
    checks += list(schema.get("exit_rules") or [])
    checks += list(schema.get("risk_rules") or [])
    return checks


def compile_strategy_text(
    raw_strategy: str,
    llm: LLMClient,
    config: StockConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Compile raw strategy text -> {schema, compiled_prompt, checks}."""
    prompt = render("strategy_compile", raw_strategy=raw_strategy.strip())
    out = llm.complete(
        system="You compile trading strategies into strict JSON. Output JSON only.",
        user=prompt,
        model=config.strategy.compile_model,
        temperature=config.strategy.compile_temperature,
        response_format="json",
    )
    try:
        parsed = extract_json(out)
    except ValueError:
        parsed = {}
    schema = _normalize_schema(parsed)
    return {
        "schema": schema,
        "compiled_prompt": render_compiled_prompt(schema),
        "checks": _collect_checks(schema),
    }


def load_raw_strategy(
    *,
    raw_text: Optional[str] = None,
    strategy_path: Optional[str] = None,
) -> str:
    """Resolve raw strategy from inline text or a local file (no URL/Git)."""
    if raw_text and raw_text.strip():
        return raw_text
    if strategy_path:
        path = os.path.expanduser(strategy_path)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise ValueError("必须提供 raw_text 或 strategy_path 之一")


def compile_strategy(
    ctx: ResearchContext,
    llm: LLMClient,
    *,
    raw_text: Optional[str] = None,
    strategy_path: Optional[str] = None,
    source: str = "user",
    config: StockConfig = DEFAULT_CONFIG,
) -> ResearchContext:
    """Compile a strategy and write the result into ``ctx.strategy``."""
    raw = load_raw_strategy(raw_text=raw_text, strategy_path=strategy_path)
    result = compile_strategy_text(raw, llm, config)
    ctx.strategy = StrategySlot(
        compiled_prompt=result["compiled_prompt"],
        source=source,
        raw_ref=strategy_path or "(inline)",
        schema=result["schema"],
        checks=result["checks"],
    )
    return ctx

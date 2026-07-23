"""Module 4: Analysis sub-agent — 6-stage pipeline (the centerpiece).

The analysis has too much to do for one prompt (read research, read K-line,
check the strategy rule-by-rule, and serve four decision scenarios), so it's
split into six sequential stages. Each stage is one LLM call with an explicit
input/output contract; the previous stage's output feeds the next.

    S1 fundamental_view   <- research.digest
    S2 technical_view     <- kline.features (often placeholder this release)
    S3 strategy_fit       <- strategy.compiled + S1 + S2
    S4 synthesis + route  <- S1 + S2 + S3  (decides decision_type)
    S5 verdict            <- S4 (branch by decision_type)
    S6 risk_and_exec      <- S5 + strategy.risk_rules

Stage gating = scheme B: the fact-extraction stages (S1/S2/S3) self-validate and
retry up to ``fact_stage_max_retries``; S4-S6 run once, then a single final judge
may trigger ONE corrective re-run of S4-S6.

Standalone entry point: ``run_analysis(ctx, llm, judge_llm, config)``.
Hermes tool wrapper: see ``hermes_tools/stock_analysis_tool.py``.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from .config import StockConfig, DEFAULT_CONFIG
from .context import ResearchContext
from .llm import LLMClient, extract_json
from .templates import render


_VALID_DECISION_TYPES = ("stock_pick", "timing", "sector", "portfolio")


def _call_json(
    llm: LLMClient,
    system: str,
    template: str,
    config: StockConfig,
    **kw: str,
) -> Dict[str, Any]:
    """Render a stage template, call the LLM, and parse JSON (empty on failure)."""
    prompt = render(template, **kw)
    out = llm.complete(
        system=system,
        user=prompt,
        model=config.analysis.model,
        temperature=config.analysis.temperature,
        response_format="json",
    )
    try:
        return extract_json(out) or {}
    except ValueError:
        return {}


def _run_fact_stage(
    validate: Callable[[Dict[str, Any]], bool],
    produce: Callable[[], Dict[str, Any]],
    config: StockConfig,
) -> Dict[str, Any]:
    """Scheme B: produce a fact stage, self-validate, retry up to the cap.

    Retries are independent re-samples (no feedback), matching the deep-research
    philosophy. Returns the last attempt even if it never validated.
    """
    result: Dict[str, Any] = {}
    for _ in range(config.analysis.fact_stage_max_retries + 1):
        result = produce()
        if validate(result):
            return result
    return result


# ---- stage runners --------------------------------------------------------

def stage_s1_fundamental(ctx, llm, config) -> Dict[str, Any]:
    sources = ctx.research.sources or []
    indexed = "\n".join(
        f"[{i}] {json.dumps(s, ensure_ascii=False)}" for i, s in enumerate(sources)
    ) or "(无来源)"

    def produce():
        return _call_json(
            llm, "You are a rigorous equity research analyst. Output JSON only.",
            "analysis_s1_fundamental", config,
            target=ctx.query.target,
            question=ctx.query.question or "(未指定)",
            horizon=ctx.query.horizon or "(未指定)",
            digest=ctx.research.digest or "(空)",
            sources=indexed,
        )

    def validate(r):
        # every evidence item must point at a real source index
        ev = r.get("evidence") or []
        if not isinstance(ev, list):
            return False
        n = len(sources)
        for e in ev:
            idx = (e or {}).get("source_idx")
            if not isinstance(idx, int) or idx < 0 or (n and idx >= n):
                return False
        return "bull_points" in r or "bear_points" in r

    return _run_fact_stage(validate, produce, config)


def stage_s2_technical(ctx, llm, config) -> Dict[str, Any]:
    features = ctx.kline.features or {}
    has_data = any(v is not None for v in features.values())

    if not has_data:
        # No K-line data (placeholder). Skip the LLM entirely and be honest.
        return {
            "available": False, "trend": None, "position": None, "volume": None,
            "signals": [], "key_levels": {"support": None, "resistance": None},
            "confidence": 0.0,
        }

    def produce():
        return _call_json(
            llm, "You are a disciplined technical analyst. Output JSON only.",
            "analysis_s2_technical", config,
            target=ctx.query.target,
            horizon=ctx.query.horizon or "(未指定)",
            features=json.dumps(features, ensure_ascii=False),
        )

    def validate(r):
        return "available" in r

    return _run_fact_stage(validate, produce, config)


def stage_s3_strategy_fit(ctx, llm, config, s1, s2) -> Dict[str, Any]:
    strategy_block = ctx.strategy.compiled_prompt or "(未提供策略)"

    def produce():
        return _call_json(
            llm, "You check strategy rule compliance precisely. Output JSON only.",
            "analysis_s3_strategy_fit", config,
            target=ctx.query.target,
            horizon=ctx.query.horizon or "(未指定)",
            strategy=strategy_block,
            fundamental_view=json.dumps(s1, ensure_ascii=False),
            technical_view=json.dumps(s2, ensure_ascii=False),
        )

    def validate(r):
        return "fit_score" in r or "entry" in r

    return _run_fact_stage(validate, produce, config)


def stage_s4_synthesis(ctx, llm, config, s1, s2, s3) -> Dict[str, Any]:
    hint = ctx.query.decision_type if ctx.query.decision_type in _VALID_DECISION_TYPES else "(auto)"
    r = _call_json(
        llm, "You synthesize views and route decisions. Output JSON only.",
        "analysis_s4_synthesis", config,
        target=ctx.query.target,
        question=ctx.query.question or "(未指定)",
        horizon=ctx.query.horizon or "(未指定)",
        fundamental_view=json.dumps(s1, ensure_ascii=False),
        technical_view=json.dumps(s2, ensure_ascii=False),
        strategy_fit=json.dumps(s3, ensure_ascii=False),
        decision_type_hint=hint,
    )
    # Enforce a valid decision_type: user hint wins; else model's; else fallback.
    dt = r.get("decision_type")
    if ctx.query.decision_type in _VALID_DECISION_TYPES:
        dt = ctx.query.decision_type
    elif dt not in _VALID_DECISION_TYPES:
        dt = "timing"
    r["decision_type"] = dt
    return r


def stage_s5_verdict(ctx, llm, config, s1, s2, s3, s4) -> Dict[str, Any]:
    return _call_json(
        llm, "You produce the final investment verdict. Output JSON only.",
        "analysis_s5_verdict", config,
        target=ctx.query.target,
        question=ctx.query.question or "(未指定)",
        horizon=ctx.query.horizon or "(未指定)",
        synthesis=json.dumps(s4.get("synthesis", {}), ensure_ascii=False),
        strategy_fit=json.dumps(s3, ensure_ascii=False),
        fundamental_view=json.dumps(s1, ensure_ascii=False),
        technical_view=json.dumps(s2, ensure_ascii=False),
        decision_type=s4.get("decision_type", "timing"),
    )


def stage_s6_risk_exec(ctx, llm, config, s2, s5) -> Dict[str, Any]:
    risk_rules = (ctx.strategy.schema or {}).get("risk_rules") or []
    technical_note = "技术面数据可用" if s2.get("available") else "技术面数据缺失（K线占位），置信度需打折"
    return _call_json(
        llm, "You are a risk and execution officer. Output JSON only.",
        "analysis_s6_risk_exec", config,
        target=ctx.query.target,
        horizon=ctx.query.horizon or "(未指定)",
        verdict=json.dumps(s5, ensure_ascii=False),
        risk_rules="\n".join(f"- {x}" for x in risk_rules) or "(未提供)",
        technical_note=technical_note,
    )


def judge_analysis(ctx, llm, config, s4, s5, s6) -> Dict[str, Any]:
    prompt = render(
        "analysis_judge",
        target=ctx.query.target,
        question=ctx.query.question or "(未指定)",
        synthesis=json.dumps(s4.get("synthesis", {}), ensure_ascii=False),
        verdict=json.dumps(s5, ensure_ascii=False),
        risk_and_exec=json.dumps(s6, ensure_ascii=False),
    )
    out = llm.complete(
        system="You are a strict analysis-quality judge. Output JSON only.",
        user=prompt,
        model=config.research.judge_model,
        temperature=0.0,
        response_format="json",
    )
    try:
        parsed = extract_json(out) or {}
    except ValueError:
        parsed = {}
    try:
        score = float(parsed.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "score": max(0.0, min(10.0, score)),
        "reasons": str(parsed.get("reasons", "")),
        "worst_gap": str(parsed.get("worst_gap", "")),
    }


def run_analysis(
    ctx: ResearchContext,
    llm: LLMClient,
    judge_llm: Optional[LLMClient] = None,
    config: StockConfig = DEFAULT_CONFIG,
    *,
    persist: bool = True,
) -> ResearchContext:
    """Run the 6-stage pipeline and write results into ``ctx.analysis``.

    Fact stages (S1/S2/S3) self-validate & retry (scheme B). S4-S6 run once;
    if the final judge is enabled and scores below threshold, S4-S6 re-run ONCE.
    """
    judge_llm = judge_llm or llm

    s1 = stage_s1_fundamental(ctx, llm, config)
    s2 = stage_s2_technical(ctx, llm, config)
    s3 = stage_s3_strategy_fit(ctx, llm, config, s1, s2)

    def run_tail():
        _s4 = stage_s4_synthesis(ctx, llm, config, s1, s2, s3)
        _s5 = stage_s5_verdict(ctx, llm, config, s1, s2, s3, _s4)
        _s6 = stage_s6_risk_exec(ctx, llm, config, s2, _s5)
        return _s4, _s5, _s6

    s4, s5, s6 = run_tail()
    verdict_judge: Dict[str, Any] = {}
    if config.analysis.final_judge_enabled:
        verdict_judge = judge_analysis(ctx, judge_llm, config, s4, s5, s6)
        if verdict_judge["score"] < config.analysis.final_judge_threshold:
            # One corrective re-run of the reasoning tail (no feedback).
            s4, s5, s6 = run_tail()
            verdict_judge = judge_analysis(ctx, judge_llm, config, s4, s5, s6)

    ctx.analysis = {
        "fundamental_view": s1,
        "technical_view": s2,
        "strategy_fit": s3,
        "synthesis": s4.get("synthesis", {}),
        "decision_type": s4.get("decision_type", "timing"),
        "verdict": s5,
        "risk_and_exec": s6,
        "quality": verdict_judge,
    }
    if persist:
        _persist_analysis(ctx, config.workdir)
        ctx.save(config.workdir)
    return ctx


def _persist_analysis(ctx: ResearchContext, workdir: str) -> None:
    import os
    adir = ctx.run_dir(workdir)
    with open(os.path.join(adir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(ctx.analysis, f, ensure_ascii=False, indent=2)

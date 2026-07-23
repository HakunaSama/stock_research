"""Module 3: DeepResearch with judge scoring + no-feedback retry.

The loop borrows the keep/discard idea from autoresearch's program.md: run a
research pass, score it with an INDEPENDENT judge, and if it doesn't clear the
bar, retry — WITHOUT feeding the judge's critique back (the design explicitly
wants independent re-sampling, not "teaching to the test"). Retry diversity
comes primarily from angle rotation + retrieval-facet rotation, with a small
temperature bump as a secondary perturbation.

The research *producer* is pluggable:
- standalone: an injected callable or a plain LLM call (``LLMResearcher``),
- hermes: a ``delegate_task`` subagent (see ``hermes_tools/stock_research_tool.py``).

Entry point: ``run_deep_research(ctx, researcher, judge_llm, config)``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .config import StockConfig, DEFAULT_CONFIG
from .context import ResearchContext, ResearchSlot
from .llm import LLMClient, extract_json
from .templates import render


# Angles rotated across attempts to force coverage of different info facets.
_ANGLES = [
    "最新财报、业绩指引与关键财务数据",
    "分析师/研究机构评级变化与目标价",
    "近期新闻、公告与价格异动事件",
    "供应链、需求端与行业竞争格局",
    "市场情绪、资金流向与持仓变化",
    "监管、诉讼与其他重大风险事件",
    "宏观与板块层面的驱动因子",
    "估值水平与同业对比",
]


class Researcher(Protocol):
    """Produces a research result for one attempt.

    Returns a dict: {"digest": str, "sources": [ {title,url,date}, ... ]}.
    ``angle`` and ``temperature`` are the diversity levers for this attempt.
    """

    def __call__(
        self, *, ctx: ResearchContext, angle: str, temperature: float, attempt: int
    ) -> Dict[str, Any]:
        ...


@dataclass
class LLMResearcher:
    """Simple researcher backed by a single LLM call (no live web).

    Useful standalone/testing. In production the hermes wrapper uses a
    ``delegate_task`` subagent with real web_search/web_extract tools instead.
    """

    llm: LLMClient
    model: Optional[str] = None

    def __call__(self, *, ctx, angle, temperature, attempt):
        prompt = render(
            "research_task",
            target=ctx.query.target,
            question=ctx.query.question or "(未指定)",
            horizon=ctx.query.horizon or "(未指定)",
            angle=angle,
        )
        out = self.llm.complete(
            system="You are a rigorous equity research analyst. Output JSON only.",
            user=prompt,
            model=self.model,
            temperature=temperature,
            response_format="json",
        )
        try:
            parsed = extract_json(out)
        except ValueError:
            parsed = {}
        return {
            "digest": str((parsed or {}).get("digest", "")),
            "sources": list((parsed or {}).get("sources", []) or []),
        }


def build_researcher(
    llm: LLMClient, config: StockConfig = DEFAULT_CONFIG, *, retriever=None
) -> Researcher:
    """Pick the research producer per config.

    - ``engine == "odr"``  -> multi-agent OpenDeepResearcher (default)
    - ``engine == "legacy"`` -> single-shot LLMResearcher

    ``retriever`` (ODR only) injects how each sub-topic is investigated: default
    is a single-LLM stub; hermes passes a web_search/web_extract subagent.

    Either way the OUTER judge/retry loop in ``run_deep_research`` is identical:
    a below-threshold result re-runs the whole producer — so with ODR selected,
    a low final-report score re-runs the entire ODR flow.
    """
    if config.research.engine == "odr":
        from .odr import OpenDeepResearcher

        return OpenDeepResearcher(llm=llm, config=config, retriever=retriever)
    return LLMResearcher(llm=llm, model=config.research.research_model)


def judge_digest(
    ctx: ResearchContext,
    digest: str,
    sources: List[Dict[str, Any]],
    judge_llm: LLMClient,
    config: StockConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Independent judge call. Returns {score, reasons, worst_gap}."""
    prompt = render(
        "research_judge",
        target=ctx.query.target,
        question=ctx.query.question or "(未指定)",
        horizon=ctx.query.horizon or "(未指定)",
        digest=digest or "(空)",
        source_count=str(len(sources)),
        sources=json.dumps(sources, ensure_ascii=False)[:4000],
    )
    out = judge_llm.complete(
        system="You are a strict research-quality judge. Output JSON only.",
        user=prompt,
        model=config.research.judge_model,
        temperature=0.0,
        response_format="json",
    )
    try:
        parsed = extract_json(out)
    except ValueError:
        parsed = {}
    try:
        score = float((parsed or {}).get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "score": max(0.0, min(10.0, score)),
        "reasons": str((parsed or {}).get("reasons", "")),
        "worst_gap": str((parsed or {}).get("worst_gap", "")),
    }


def _persist_attempt(ctx: ResearchContext, workdir: str, attempt: int, payload: Dict[str, Any]) -> None:
    rdir = os.path.join(ctx.run_dir(workdir), "research")
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, f"attempt_{attempt}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_deep_research(
    ctx: ResearchContext,
    researcher: Researcher,
    judge_llm: LLMClient,
    config: StockConfig = DEFAULT_CONFIG,
    *,
    persist: bool = True,
) -> ResearchContext:
    """Run the judge/retry loop and write the accepted digest into ctx.research.

    - accept as soon as score >= threshold
    - otherwise keep the best-so-far and retry (NO feedback to the researcher)
    - stop at max_attempts; if never cleared, take best-effort with a note
    """
    rc = config.research
    best: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = []

    def _trace_of() -> Dict[str, Any]:
        """Pull the ODR trace for the just-finished attempt, if the producer
        exposes one (OpenDeepResearcher stores it on ``last_result``)."""
        last = getattr(researcher, "last_result", None)
        if last is not None and hasattr(last, "to_trace_dict"):
            return last.to_trace_dict()
        return {}

    for attempt in range(1, rc.max_attempts + 1):
        angle = _ANGLES[(attempt - 1) % len(_ANGLES)]
        temperature = min(
            rc.temperature_cap,
            rc.base_temperature + (attempt - 1) * rc.temperature_step,
        )

        produced = researcher(ctx=ctx, angle=angle, temperature=temperature, attempt=attempt)
        digest = str(produced.get("digest", ""))
        sources = list(produced.get("sources", []) or [])

        verdict = judge_digest(ctx, digest, sources, judge_llm, config)
        score = verdict["score"]
        trace = _trace_of()

        # Record one history entry per attempt (each is a full ODR re-run when
        # engine=="odr"): score + judge verdict + a compact trace summary.
        history.append({
            "attempt": attempt,
            "angle": angle,
            "temperature": round(temperature, 3),
            "score": score,
            "accepted": score >= rc.threshold,
            "judge": verdict,
            "supervisor_rounds": trace.get("supervisor_rounds", 0),
            "sub_topics": [f.get("topic", "") for f in trace.get("findings", [])],
        })

        if persist:
            _persist_attempt(
                ctx, config.workdir, attempt,
                {
                    "attempt": attempt, "angle": angle, "temperature": temperature,
                    "score": score, "judge": verdict,  # reasons logged, NOT reused
                    "digest": digest, "sources": sources,
                    "odr": trace,  # full ODR trace for this attempt
                },
            )

        if best is None or score > best["score"]:
            best = {"digest": digest, "sources": sources, "score": score, "odr": trace}

        if score >= rc.threshold:
            ctx.research = ResearchSlot(
                status="accepted", score=score, attempts=attempt,
                threshold=rc.threshold,
                digest=digest, sources=sources,
                engine=rc.engine, history=history, odr=trace,
            )
            if persist:
                ctx.save(config.workdir)
            return ctx
        # else: retry WITHOUT feeding verdict["reasons"] back to the researcher.

    # Exhausted attempts — take the best-effort result, flagged.
    assert best is not None
    ctx.research = ResearchSlot(
        status="best_effort", score=best["score"], attempts=rc.max_attempts,
        threshold=rc.threshold,
        digest=best["digest"], sources=best["sources"],
        note=f"未达阈值 {rc.threshold}，{rc.max_attempts} 次重试后取最优（{best['score']:.1f}）。",
        engine=rc.engine, history=history, odr=best.get("odr", {}),
    )
    if persist:
        ctx.save(config.workdir)
    return ctx

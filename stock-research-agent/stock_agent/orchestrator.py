"""Orchestrator: chain the four modules into one run.

    strategy_compile -> deep_research -> kline_fetch -> analysis

Threads a single ``ResearchContext`` through all stages and persists it. Used by
the standalone demo and by the hermes orchestrator skill (which can instead call
the individual tools so the agent narrates each step).
"""

from __future__ import annotations

from typing import Optional

from .config import StockConfig, DEFAULT_CONFIG
from .context import ResearchContext
from .llm import LLMClient
from .strategy import compile_strategy
from .research import run_deep_research, build_researcher, Researcher
from .kline import fetch_kline
from .analysis import run_analysis


def run_pipeline(
    *,
    target: str,
    question: str = "",
    horizon: str = "",
    decision_type: Optional[str] = None,
    strategy_text: Optional[str] = None,
    strategy_path: Optional[str] = None,
    strategy_source: str = "user",
    llm: LLMClient,
    judge_llm: Optional[LLMClient] = None,
    researcher: Optional[Researcher] = None,
    kline_symbol: str = "",
    kline_timeframe: str = "1d",
    kline_range: str = "6mo",
    config: StockConfig = DEFAULT_CONFIG,
    persist: bool = True,
) -> ResearchContext:
    """Run the full stock-research pipeline end to end.

    ``llm`` powers strategy compile + analysis. ``judge_llm`` (defaults to
    ``llm``) scores research and the final verdict. ``researcher`` defaults to
    the engine chosen by ``config.research.engine`` (``odr`` => multi-agent
    OpenDeepResearcher; ``legacy`` => single-shot LLMResearcher). In hermes a
    delegate-backed researcher may be injected instead.
    """
    judge_llm = judge_llm or llm
    researcher = researcher or build_researcher(llm, config)

    ctx = ResearchContext.new(
        target=target, question=question, horizon=horizon, decision_type=decision_type
    )

    if strategy_text or strategy_path:
        compile_strategy(
            ctx, llm,
            raw_text=strategy_text, strategy_path=strategy_path,
            source=strategy_source, config=config,
        )

    run_deep_research(ctx, researcher, judge_llm, config, persist=persist)
    fetch_kline(
        ctx, symbol=kline_symbol or target,
        timeframe=kline_timeframe, range=kline_range, config=config,
    )
    run_analysis(ctx, llm, judge_llm, config, persist=persist)

    if persist:
        ctx.save(config.workdir)
    return ctx

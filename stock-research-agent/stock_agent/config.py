"""Configuration for the stock-research agent.

All knobs the design doc marked "configurable" live here. In hermes these map to
the ``stock:`` section of ``cli-config.yaml``; standalone callers can build a
``StockConfig`` directly or via ``StockConfig.from_dict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


@dataclass
class StrategyConfig:
    # Model used to compile a raw strategy into structured schema.
    # None => fall back to the cheap delegation-tier model in hermes.
    compile_model: Optional[str] = None
    compile_temperature: float = 0.2
    # Local-only strategy library root (no URL/Git fetch by design).
    library_dir: str = "skills/stock/strategies"


@dataclass
class ODRConfig:
    """Open-Deep-Research engine (multi-agent supervisor + parallel sub-research).

    A faithful pure-Python port of langchain-ai/open_deep_research's *approach*
    (no LangGraph dependency). Toggle it with ``engine`` on ResearchConfig; when
    off we fall back to the legacy single-shot ``LLMResearcher``.
    """
    # Step 1 of ODR — clarify ambiguous requests by asking the user back.
    # OFF by default: our pipeline is meant to run autonomously (no human in
    # the loop). Flip on for interactive sessions.
    clarify_enabled: bool = False
    # Supervisor loop: how many rounds it may delegate sub-research.
    max_supervisor_iterations: int = 4
    # Each sub-researcher's ReAct tool-call budget (search + think_tool).
    max_researcher_iterations: int = 6
    # Fan-out: how many sub-topics run in parallel per supervisor round.
    max_concurrent_units: int = 4
    # Per-stage model routing (None => fall back to research_model / main).
    summarization_model: Optional[str] = None
    research_model: Optional[str] = None
    compression_model: Optional[str] = None
    final_report_model: Optional[str] = None
    # Temperatures per stage.
    supervisor_temperature: float = 0.3
    researcher_temperature: float = 0.5
    compression_temperature: float = 0.2
    final_report_temperature: float = 0.3


@dataclass
class ResearchConfig:
    threshold: float = 8.0          # accept digest when judge score >= this
    max_attempts: int = 8           # hard cap on no-feedback retries
    judge_model: Optional[str] = None   # None => same as main model
    research_model: Optional[str] = None
    base_temperature: float = 0.4
    temperature_step: float = 0.1   # +step per retry (diversity, secondary)
    temperature_cap: float = 0.9
    # Which producer drives one attempt: "odr" (multi-agent) or "legacy"
    # (single-shot LLMResearcher). The judge/retry OUTER loop is identical for
    # both — a low-scoring ODR report simply re-runs the whole ODR flow.
    engine: str = "odr"
    odr: ODRConfig = field(default_factory=ODRConfig)


@dataclass
class KlineConfig:
    """K-line (OHLCV) fetch + feature extraction.

    The bars are pulled from the vendored ``stocksdk`` (free A-share sources:
    tencent/eastmoney/sina, auto failover). Everything degrades gracefully: if
    a fetch fails the slot falls back to ``status="placeholder"`` and no other
    module changes.
    """
    enabled: bool = True            # off => fetch_kline stays a placeholder
    period: str = "day"             # stocksdk period: 1m/5m/15m/30m/60m/day/week/month
    count: int = 120                # how many bars to pull (enough for MA60 + margin)
    adjust: str = "qfq"             # qfq 前复权 / hfq 后复权 / none 不复权
    timeout: float = 6.0            # per-request seconds
    # Moving-average windows the feature extractor computes.
    ma_windows: tuple = (5, 10, 20, 60)


@dataclass
class AnalysisConfig:
    model: Optional[str] = None
    temperature: float = 0.3
    # Stage gating "B": fact-extraction stages self-validate & retry.
    fact_stage_max_retries: int = 2
    # Final verdict quality gate (single check at the end).
    final_judge_enabled: bool = True
    final_judge_threshold: float = 7.0  # below => one corrective re-run of S4-S6


@dataclass
class StockConfig:
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    kline: KlineConfig = field(default_factory=KlineConfig)
    # Root for run artifacts (context.json, research attempts, ...).
    workdir: str = "~/.hermes/stock"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StockConfig":
        data = data or {}
        research_data = dict(data.get("research") or {})
        odr_data = research_data.pop("odr", None)
        research = ResearchConfig(**research_data)
        if odr_data:
            research.odr = ODRConfig(**odr_data)
        return cls(
            strategy=StrategyConfig(**(data.get("strategy") or {})),
            research=research,
            analysis=AnalysisConfig(**(data.get("analysis") or {})),
            kline=KlineConfig(**(data.get("kline") or {})),
            workdir=data.get("workdir", "~/.hermes/stock"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CONFIG = StockConfig()

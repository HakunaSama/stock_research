"""ResearchContext — the shared data contract that threads the four modules.

Strategy -> Research -> K-line -> Analysis -> Verdict all read/write one object
so nothing is passed by word of mouth. Persisted as JSON under
``<workdir>/<run_id>/context.json`` for debugging and reproducibility.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List, Optional


DecisionType = str  # one of: stock_pick | timing | sector | portfolio


@dataclass
class Query:
    target: str                       # ticker / basket / sector label
    question: str = ""                # free-text research question
    horizon: str = ""                 # e.g. "1-3 个月"
    decision_type: Optional[DecisionType] = None  # user-specified; else S4 decides


@dataclass
class StrategySlot:
    compiled_prompt: str = ""
    source: str = ""                  # "user" | "bigv:<name>"
    raw_ref: str = ""                 # path to strategy.md
    schema: Dict[str, Any] = field(default_factory=dict)  # structured rules
    checks: List[str] = field(default_factory=list)


@dataclass
class KlineSlot:
    status: str = "placeholder"       # placeholder | ok | error
    symbol: str = ""
    timeframe: str = ""
    range: str = ""
    features: Optional[Dict[str, Any]] = None
    raw_ref: Optional[str] = None


@dataclass
class ResearchSlot:
    status: str = "pending"           # pending | accepted | best_effort
    score: float = 0.0
    attempts: int = 0
    threshold: float = 0.0            # accept bar this run was gated against
    digest: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    note: str = ""                    # e.g. "未达阈值，取最优"
    engine: str = ""                  # "odr" | "legacy"
    # Per-attempt judge history (each ODR re-run appends one entry): so the UI
    # can show "scored 5.0 -> re-ran ODR -> 5.5 -> ... -> 8.5 accepted".
    history: List[Dict[str, Any]] = field(default_factory=list)
    # Full ODR trace of the ACCEPTED (or best) attempt: brief, sub-findings,
    # compressed notes, supervisor rounds. Empty for the legacy engine.
    odr: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchContext:
    run_id: str
    query: Query
    strategy: StrategySlot = field(default_factory=StrategySlot)
    kline: KlineSlot = field(default_factory=KlineSlot)
    research: ResearchSlot = field(default_factory=ResearchSlot)
    analysis: Dict[str, Any] = field(default_factory=dict)  # filled by S1..S6

    # ---- construction -----------------------------------------------------
    @classmethod
    def new(
        cls,
        target: str,
        question: str = "",
        horizon: str = "",
        decision_type: Optional[str] = None,
        suffix: str = "x1",
    ) -> "ResearchContext":
        run_id = f"{date.today().isoformat()}-{_slug(target)}-{suffix}"
        return cls(
            run_id=run_id,
            query=Query(
                target=target,
                question=question,
                horizon=horizon,
                decision_type=decision_type,
            ),
        )

    # ---- (de)serialization ------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchContext":
        q = data.get("query", {})
        ctx = cls(run_id=data["run_id"], query=Query(**q))
        if data.get("strategy"):
            ctx.strategy = StrategySlot(**data["strategy"])
        if data.get("kline"):
            ctx.kline = KlineSlot(**data["kline"])
        if data.get("research"):
            ctx.research = ResearchSlot(**data["research"])
        ctx.analysis = data.get("analysis", {}) or {}
        return ctx

    # ---- persistence ------------------------------------------------------
    def run_dir(self, workdir: str) -> str:
        base = os.path.expanduser(workdir)
        path = os.path.join(base, self.run_id)
        os.makedirs(path, exist_ok=True)
        return path

    def save(self, workdir: str) -> str:
        path = os.path.join(self.run_dir(workdir), "context.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "ResearchContext":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def _slug(text: str) -> str:
    keep = [c if (c.isalnum() or c in "-_") else "-" for c in text.strip()]
    return "".join(keep)[:24] or "run"

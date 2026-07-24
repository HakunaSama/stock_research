"""OpenDeepResearcher — a pure-Python port of langchain-ai/open_deep_research.

This is the ODR *approach* (multi-agent supervisor + parallel sub-research +
reflection + compression + report writing) implemented with plain function
calls instead of a LangGraph state machine. It satisfies the existing
``Researcher`` protocol (``__call__(...) -> {"digest", "sources"}``), so it is a
drop-in producer for the judge/retry loop in ``research.py``.

Stages (mirroring ODR's graph nodes):

    clarify_with_user      # optional (config.odr.clarify_enabled), off by default
      -> write_research_brief
        -> supervisor loop (up to max_supervisor_iterations):
             supervisor plans -> delegate N sub-topics (parallel) ->
             each sub-researcher runs a bounded ReAct+think loop ->
             compress each finding -> feed notes back to supervisor
        -> final_report_generation

How this composes with your requirement:
- ODR produces ONE final report per call (one outer attempt).
- ``run_deep_research`` scores that report with an INDEPENDENT judge; if it is
  below threshold, the whole ODR flow re-runs (next attempt) — exactly "re-run
  the ODR process when the final score is too low".

Concurrency note: ODR runs sub-researchers in parallel. We use a thread pool so
blocking LLM HTTP calls overlap; with FakeLLM it simply runs fast. Ordering of
results is normalized so runs are reproducible.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import StockConfig, DEFAULT_CONFIG
from ..context import ResearchContext
from ..llm import LLMClient, extract_json
from ..templates import render
from .retriever import Retriever, LLMSubResearcher
from .state import (
    ResearchBrief,
    SubTopic,
    SubFinding,
    CompressedNote,
    ODRResult,
)


def _safe_json(text: str) -> Dict[str, Any]:
    try:
        parsed = extract_json(text)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class OpenDeepResearcher:
    """ODR engine as a Researcher. One ``__call__`` == one full ODR run.

    ``llm`` powers every stage; per-stage model routing comes from
    ``config.research.odr.*_model`` (None => fall back to the research model,
    then to the client's default).

    ``retriever`` powers each sub-topic investigation. Defaults to
    ``LLMSubResearcher`` (single LLM call, no live web). In hermes a
    delegate-backed retriever (web_search/web_extract subagent) is injected so
    sub-research is grounded in real sources.

    ``last_result`` holds the most recent run's full ODRResult (brief, notes,
    findings, rounds) so callers can persist the ODR trace.
    """

    llm: LLMClient
    # Python 3.11+ forbids a mutable dataclass instance as a field default;
    # default_factory yields the same shared DEFAULT_CONFIG the old code used.
    config: StockConfig = field(default_factory=lambda: DEFAULT_CONFIG)
    retriever: Optional[Retriever] = None
    last_result: Optional[ODRResult] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.retriever is None:
            self.retriever = LLMSubResearcher(
                llm=self.llm, model=self.config.research.odr.research_model
            )

    # ---- Researcher protocol ---------------------------------------------
    def __call__(
        self, *, ctx: ResearchContext, angle: str, temperature: float, attempt: int
    ) -> Dict[str, Any]:
        # ``angle``/``temperature`` are the outer loop's diversity levers; ODR
        # folds ``temperature`` into its stages so retries still diversify.
        result = self.run(ctx, temperature_bias=temperature - self.config.research.base_temperature)
        self.last_result = result
        return result.to_producer_dict()

    # ---- full ODR flow ----------------------------------------------------
    def run(self, ctx: ResearchContext, *, temperature_bias: float = 0.0) -> ODRResult:
        odr = self.config.research.odr

        clarification = ""
        assumption = ""
        if odr.clarify_enabled:
            clarification, assumption = self._clarify(ctx)
            if clarification:
                # Interactive mode: surface the question instead of guessing.
                return ODRResult(clarification_needed=clarification)

        brief = self._write_brief(ctx, assumption, temperature_bias)

        notes: List[CompressedNote] = []
        all_findings: List[SubFinding] = []
        rounds = 0
        for rnd in range(1, odr.max_supervisor_iterations + 1):
            rounds = rnd
            plan = self._supervise(brief, notes, rnd, temperature_bias)
            sub_topics = plan["sub_topics"]
            if plan["complete"] or not sub_topics:
                if notes:  # only stop early if we actually have findings
                    break
                if not sub_topics:  # nothing to do and nothing gathered — bail
                    break
            findings = self._research_parallel(ctx, brief, sub_topics, temperature_bias)
            all_findings.extend(findings)
            for f in findings:
                notes.append(self._compress(f, temperature_bias))

        report = self._final_report(brief, notes, temperature_bias)
        return ODRResult(
            digest=report["digest"],
            sources=report["sources"],
            brief=brief,
            notes=notes,
            findings=all_findings,
            supervisor_rounds=rounds,
        )

    # ---- stage: clarify ---------------------------------------------------
    def _clarify(self, ctx: ResearchContext) -> tuple[str, str]:
        out = self._call(
            "odr_clarify",
            self.config.research.odr.research_model,
            self.config.research.odr.supervisor_temperature,
            system="You scope research requests. Output JSON only.",
            target=ctx.query.target,
            question=ctx.query.question or "(未指定)",
            horizon=ctx.query.horizon or "(未指定)",
        )
        if out.get("need_clarification"):
            return str(out.get("question", "")), ""
        return "", str(out.get("assumption", ""))

    # ---- stage: brief -----------------------------------------------------
    def _write_brief(
        self, ctx: ResearchContext, assumption: str, tbias: float
    ) -> ResearchBrief:
        odr = self.config.research.odr
        out = self._call(
            "odr_brief",
            odr.research_model,
            _t(odr.supervisor_temperature, tbias),
            system="You are a lead research planner. Output JSON only.",
            target=ctx.query.target,
            question=ctx.query.question or "(未指定)",
            horizon=ctx.query.horizon or "(未指定)",
            assumption=assumption or "(无)",
        )
        return ResearchBrief(
            brief=str(out.get("brief", "")) or ctx.query.target,
            sub_questions=[str(s) for s in (out.get("sub_questions") or [])],
        )

    # ---- stage: supervisor ------------------------------------------------
    def _supervise(
        self, brief: ResearchBrief, notes: List[CompressedNote], rnd: int, tbias: float
    ) -> Dict[str, Any]:
        odr = self.config.research.odr
        out = self._call(
            "odr_supervisor",
            odr.research_model,
            _t(odr.supervisor_temperature, tbias),
            system="You are the research supervisor. Output JSON only.",
            brief=brief.brief,
            sub_questions=_bullets(brief.sub_questions),
            notes_so_far=_render_notes(notes) or "(暂无)",
            round=str(rnd),
            max_rounds=str(odr.max_supervisor_iterations),
            max_units=str(odr.max_concurrent_units),
        )
        raw_topics = out.get("sub_topics") or []
        topics = [
            SubTopic(topic=str(t.get("topic", "")), rationale=str(t.get("rationale", "")))
            for t in raw_topics
            if isinstance(t, dict) and t.get("topic")
        ][: odr.max_concurrent_units]
        return {"complete": bool(out.get("complete")), "sub_topics": topics}

    # ---- stage: parallel sub-research ------------------------------------
    def _research_parallel(
        self, ctx: ResearchContext, brief: ResearchBrief, topics: List[SubTopic], tbias: float
    ) -> List[SubFinding]:
        if not topics:
            return []
        odr = self.config.research.odr
        workers = min(len(topics), max(1, odr.max_concurrent_units))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            findings = list(
                pool.map(lambda t: self._research_one(ctx, brief, t, tbias), topics)
            )
        return findings

    def _research_one(
        self, ctx: ResearchContext, brief: ResearchBrief, topic: SubTopic, tbias: float
    ) -> SubFinding:
        # Delegated to the injectable retriever: LLM stub standalone, or a
        # web_search/web_extract subagent inside hermes. Same SubFinding either way.
        odr = self.config.research.odr
        assert self.retriever is not None  # set in __post_init__
        return self.retriever(
            topic=topic,
            brief=brief.brief,
            horizon=ctx.query.horizon or "(未指定)",
            temperature=_t(odr.researcher_temperature, tbias),
        )

    # ---- stage: compress --------------------------------------------------
    def _compress(self, finding: SubFinding, tbias: float) -> CompressedNote:
        odr = self.config.research.odr
        out = self._call(
            "odr_compress",
            odr.compression_model,
            _t(odr.compression_temperature, tbias),
            system="You are a compression specialist. Output JSON only.",
            topic=finding.topic,
            notes=finding.notes or "(空)",
            sources=json.dumps(finding.sources, ensure_ascii=False)[:3000],
        )
        return CompressedNote(
            topic=finding.topic,
            compressed=str(out.get("compressed", "")) or finding.notes,
            sources=list(out.get("sources") or finding.sources),
        )

    # ---- stage: final report ---------------------------------------------
    def _final_report(
        self, brief: ResearchBrief, notes: List[CompressedNote], tbias: float
    ) -> Dict[str, Any]:
        odr = self.config.research.odr
        out = self._call(
            "odr_final_report",
            odr.final_report_model,
            _t(odr.final_report_temperature, tbias),
            system="You are the report writer. Output JSON only.",
            brief=brief.brief,
            notes=_render_notes(notes) or "(无发现)",
        )
        digest = str(out.get("digest", ""))
        sources = list(out.get("sources") or [])
        if not sources:  # fall back to merging sub-note sources
            sources = _merge_sources(notes)
        return {"digest": digest, "sources": sources}

    # ---- helpers ----------------------------------------------------------
    def _call(
        self, template: str, model: Optional[str], temperature: float, *, system: str, **kw: str
    ) -> Dict[str, Any]:
        prompt = render(template, **kw)
        text = self.llm.complete(
            system=system,
            user=prompt,
            model=model or self.config.research.odr.research_model or self.config.research.research_model,
            temperature=temperature,
            response_format="json",
        )
        return _safe_json(text)


def _t(base: float, bias: float) -> float:
    """Apply the outer-loop temperature bias, clamped to a sane range."""
    return max(0.0, min(1.0, base + bias))


def _bullets(items: List[str]) -> str:
    return "\n".join(f"- {s}" for s in items) if items else "(无)"


def _render_notes(notes: List[CompressedNote]) -> str:
    if not notes:
        return ""
    blocks = []
    for i, n in enumerate(notes, 1):
        src = json.dumps(n.sources, ensure_ascii=False)[:1500]
        blocks.append(f"[{i}] 主题：{n.topic}\n{n.compressed}\n来源：{src}")
    return "\n\n".join(blocks)


def _merge_sources(notes: List[CompressedNote]) -> List[Dict[str, Any]]:
    seen: set = set()
    merged: List[Dict[str, Any]] = []
    for n in notes:
        for s in n.sources:
            key = (s.get("url") or "", s.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            merged.append(s)
    return merged

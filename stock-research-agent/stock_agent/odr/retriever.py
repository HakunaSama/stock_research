"""Pluggable retrieval for ODR sub-researchers.

A sub-researcher investigates ONE topic and returns a ``SubFinding``. *How* it
gathers evidence is injectable via the ``Retriever`` protocol:

- standalone / tests: ``LLMSubResearcher`` — a single LLM call, no live web
  (the model answers from parametric knowledge; sources may be illustrative).
- hermes production: a delegate-backed retriever that spawns a ``delegate_task``
  subagent armed with ``web_search`` / ``web_extract`` and returns grounded
  findings. See ``hermes_tools/odr_retriever.py``.

Keeping this behind a protocol means ODR's orchestration (supervisor, parallel
fan-out, compression, report writing) is identical regardless of whether it runs
with a stub or real web retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from ..llm import LLMClient, extract_json
from ..templates import render
from .state import SubFinding, SubTopic


class Retriever(Protocol):
    """Investigates one sub-topic and returns a SubFinding.

    ``brief`` is the overall research brief (context only); the retriever must
    stay focused on ``topic``. ``temperature`` is the outer-loop diversity lever.
    """

    def __call__(
        self, *, topic: SubTopic, brief: str, horizon: str, temperature: float
    ) -> SubFinding:
        ...


@dataclass
class LLMSubResearcher:
    """Default retriever: one LLM call per sub-topic (no live web).

    Mirrors ODR's researcher node but collapses the ReAct loop into a single
    structured call — good enough standalone and for tests, and swapped for a
    real web-tool subagent inside hermes.
    """

    llm: LLMClient
    model: Optional[str] = None

    def __call__(
        self, *, topic: SubTopic, brief: str, horizon: str, temperature: float
    ) -> SubFinding:
        prompt = render(
            "odr_researcher",
            brief=brief,
            topic=topic.topic,
            rationale=topic.rationale or "(未说明)",
            horizon=horizon or "(未指定)",
        )
        text = self.llm.complete(
            system="You are a focused sub-researcher. Output JSON only.",
            user=prompt,
            model=self.model,
            temperature=temperature,
            response_format="json",
        )
        try:
            out = extract_json(text)
        except ValueError:
            out = {}
        out = out if isinstance(out, dict) else {}
        return SubFinding(
            topic=topic.topic,
            notes=str(out.get("notes", "")),
            sources=list(out.get("sources") or []),
            tool_calls=int(out.get("steps_used") or 0),
            reflections=[str(r) for r in (out.get("reflections") or [])],
        )

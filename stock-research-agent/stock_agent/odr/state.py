"""State objects for the Open-Deep-Research engine.

A pure-Python, dependency-light port of langchain-ai/open_deep_research's data
model. Where ODR uses LangGraph ``State`` TypedDicts threaded through a graph,
we use plain dataclasses threaded through function calls — same information, no
framework.

Flow the objects trace:

    ResearchBrief         # what to research (from the user's query)
      -> SubTopic[]       # supervisor decomposes brief into parallel units
        -> SubFinding     # one researcher's raw ReAct transcript + notes
          -> CompressedNote  # compression model distills each finding
    -> ODRResult          # final report + merged sources (what the judge sees)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ResearchBrief:
    """The scoped research plan derived from the user's query (ODR step 2)."""
    brief: str = ""                         # the research question, sharpened
    sub_questions: List[str] = field(default_factory=list)


@dataclass
class SubTopic:
    """One unit of research the supervisor delegates to a sub-researcher."""
    topic: str
    rationale: str = ""                     # why this angle matters


@dataclass
class SubFinding:
    """Raw output of one sub-researcher's ReAct loop (before compression)."""
    topic: str
    notes: str = ""                         # synthesized findings for this topic
    sources: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0                     # how many search/think steps it used
    reflections: List[str] = field(default_factory=list)  # think_tool traces


@dataclass
class CompressedNote:
    """A sub-finding after the compression model distills it."""
    topic: str
    compressed: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ODRResult:
    """Final ODR output. Shaped to satisfy the existing Researcher protocol.

    ``digest`` (the final report) + ``sources`` are exactly what the outer
    judge/retry loop and downstream analysis expect, so ODR is a drop-in
    producer.
    """
    digest: str = ""                        # the final report
    sources: List[Dict[str, Any]] = field(default_factory=list)
    brief: ResearchBrief = field(default_factory=ResearchBrief)
    findings: List[SubFinding] = field(default_factory=list)  # raw sub-research
    notes: List[CompressedNote] = field(default_factory=list)
    supervisor_rounds: int = 0
    clarification_needed: str = ""          # non-empty => asked user to clarify

    def to_producer_dict(self) -> Dict[str, Any]:
        """Return {digest, sources} — the shape run_deep_research consumes."""
        return {"digest": self.digest, "sources": self.sources}

    def to_trace_dict(self) -> Dict[str, Any]:
        """Serialize the full ODR trace for persistence / frontend display."""
        return {
            "brief": self.brief.brief,
            "sub_questions": list(self.brief.sub_questions),
            "supervisor_rounds": self.supervisor_rounds,
            "findings": [
                {
                    "topic": f.topic,
                    "notes": f.notes,
                    "sources": f.sources,
                    "tool_calls": f.tool_calls,
                    "reflections": f.reflections,
                }
                for f in self.findings
            ],
            "notes": [
                {"topic": n.topic, "compressed": n.compressed, "sources": n.sources}
                for n in self.notes
            ],
        }

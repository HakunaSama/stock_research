"""Hermes-only: a delegate-backed ODR retriever (real web research).

Each ODR sub-topic is handed to a hermes ``delegate_task`` subagent armed with
``web_search`` / ``web_extract``; the subagent's final answer is then structured
into a ``SubFinding``. Standalone (outside hermes) this module isn't used — ODR
falls back to the single-LLM ``LLMSubResearcher`` stub.

Design note — why a thin ``delegate`` seam:
The exact hermes delegate API (function name / signature) is resolved at runtime
in ``resolve_delegate()`` below, because it varies by hermes version and we must
not hard-code a guess. ``DelegateRetriever`` itself depends only on an injected
``delegate(instructions, tools) -> str`` callable, so the unknown surface is
isolated to one small, well-marked function. If resolution fails, callers get
``None`` and keep the LLM stub — the pipeline is identical either way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from stock_agent.llm import LLMClient, extract_json
from stock_agent.odr.state import SubFinding, SubTopic
from stock_agent.templates import render


# A delegate runs a subagent task and returns its final text answer.
DelegateFn = Callable[[str, List[str]], str]

# Tools the research subagent is allowed to use.
_RESEARCH_TOOLS = ["web_search", "web_extract"]


@dataclass
class DelegateRetriever:
    """ODR ``Retriever`` that delegates each sub-topic to a web-tool subagent.

    ``delegate(instructions, tools) -> str`` runs the subagent (hermes side).
    ``llm`` structures the subagent's free-text answer into a SubFinding (notes,
    sources, reflections). Structuring is best-effort; if it fails we still
    return the raw answer as notes so nothing is lost.
    """

    delegate: DelegateFn
    llm: LLMClient
    model: Optional[str] = None

    def __call__(
        self, *, topic: SubTopic, brief: str, horizon: str, temperature: float
    ) -> SubFinding:
        instructions = render(
            "odr_researcher",
            brief=brief,
            topic=topic.topic,
            rationale=topic.rationale or "(未说明)",
            horizon=horizon or "(未指定)",
        )
        # 1) Run the subagent with real web tools.
        answer = self.delegate(instructions, _RESEARCH_TOOLS) or ""

        # 2) Structure the free-text answer into a SubFinding.
        return self._structure(topic, answer, temperature)

    def _structure(self, topic: SubTopic, answer: str, temperature: float) -> SubFinding:
        prompt = (
            "Convert the researcher's findings below into JSON with keys "
            '"notes" (string), "sources" (list of {title,url,date}), '
            '"reflections" (list of strings), "steps_used" (int). '
            "Do not invent sources not present in the text.\n\n"
            f"===FINDINGS===\n{answer}\n===END==="
        )
        try:
            text = self.llm.complete(
                system="You extract structured research notes. Output JSON only.",
                user=prompt,
                model=self.model,
                temperature=0.0,
                response_format="json",
            )
            out = extract_json(text)
            out = out if isinstance(out, dict) else {}
        except (ValueError, Exception):  # noqa: BLE001 — degrade gracefully
            out = {}

        return SubFinding(
            topic=topic.topic,
            notes=str(out.get("notes") or answer),   # keep raw answer if parse fails
            sources=list(out.get("sources") or []),
            tool_calls=int(out.get("steps_used") or 0),
            reflections=[str(r) for r in (out.get("reflections") or [])],
        )


def resolve_delegate() -> Optional[DelegateFn]:
    """Best-effort: find hermes' delegate/subagent entry point at runtime.

    Returns a ``delegate(instructions, tools) -> str`` callable, or ``None`` if
    this hermes build doesn't expose a delegation API we recognize (then ODR
    keeps the LLM stub). We try a few known shapes without hard-failing.

    TODO(hermes-delegate): pin to the exact API once a concrete hermes version
    is available. The reference checkout was empty at implementation time, so we
    probe rather than assume.
    """
    # Shape A: a module-level helper, e.g. agent.delegation.delegate_task(...)
    for modname, attr in (
        ("agent.delegation", "delegate_task"),
        ("agent.subagent", "delegate_task"),
        ("tools.delegate_tool", "delegate_task"),
    ):
        fn = _try_import(modname, attr)
        if fn is not None:
            return _wrap_callable(fn)

    # Shape B: the registry exposes a "delegate_task" tool we can invoke.
    handler = _try_registry_tool("delegate_task")
    if handler is not None:
        return _wrap_registry_handler(handler)

    return None


def _try_import(modname: str, attr: str) -> Optional[Callable[..., Any]]:
    try:
        mod = __import__(modname, fromlist=[attr])
        return getattr(mod, attr, None)
    except Exception:  # noqa: BLE001
        return None


def _try_registry_tool(name: str) -> Optional[Callable[..., Any]]:
    try:
        from tools.registry import registry  # type: ignore

        entry = registry.get(name) if hasattr(registry, "get") else None
        if entry is None:
            return None
        return getattr(entry, "handler", None) or (entry if callable(entry) else None)
    except Exception:  # noqa: BLE001
        return None


def _wrap_callable(fn: Callable[..., Any]) -> DelegateFn:
    def _delegate(instructions: str, tools: List[str]) -> str:
        try:
            return str(fn(task=instructions, tools=tools))
        except TypeError:
            # Fall back to positional if the kwarg names differ.
            return str(fn(instructions))
    return _delegate


def _wrap_registry_handler(handler: Callable[..., Any]) -> DelegateFn:
    def _delegate(instructions: str, tools: List[str]) -> str:
        return str(handler({"task": instructions, "tools": tools}))
    return _delegate

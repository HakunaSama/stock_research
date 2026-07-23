"""Pluggable LLM client abstraction.

The stock-research modules never import a concrete LLM SDK directly. Instead they
take an ``LLMClient`` so the same code runs:

- in tests / standalone via ``FakeLLM``,
- inside hermes via ``HermesLLM`` (wraps the agent's model call),
- against any OpenAI-compatible endpoint via ``OpenAICompatibleLLM``.

An ``LLMClient`` exposes a single ``complete()`` method. ``response_format`` may
be set to ``"json"`` to hint the model to return a JSON object; callers still
defensively parse.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol


class LLMClient(Protocol):
    """Minimal interface every LLM backend must satisfy."""

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.4,
        response_format: Optional[str] = None,
    ) -> str:
        """Return the model's text completion for a single system+user turn."""
        ...


def extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON value from an LLM response.

    Handles bare JSON, ```json fenced blocks, and leading/trailing prose.
    Raises ``ValueError`` if nothing parseable is found.
    """
    if text is None:
        raise ValueError("empty LLM response")
    stripped = text.strip()
    # Try direct parse first.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fenced code block ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    # First balanced {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in LLM response: {text[:200]!r}")


@dataclass
class FakeLLM:
    """Deterministic stub LLM for standalone runs and tests.

    ``responder`` maps (system, user) -> completion string. If omitted, returns
    a canned JSON object so pipelines run end to end without a real model.
    """

    responder: Optional[Callable[[str, str], str]] = None
    calls: list = field(default_factory=list)

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.4,
        response_format: Optional[str] = None,
    ) -> str:
        self.calls.append(
            {"system": system, "user": user, "model": model, "temperature": temperature}
        )
        if self.responder is not None:
            return self.responder(system, user)
        return "{}"


@dataclass
class OpenAICompatibleLLM:
    """Thin wrapper over any OpenAI-compatible chat completions endpoint.

    Kept dependency-light: the actual HTTP client is injected as ``call_fn`` so
    this module needs no SDK. ``call_fn(messages, model, temperature)`` must
    return the assistant message content string.
    """

    call_fn: Callable[..., str]
    default_model: Optional[str] = None

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.4,
        response_format: Optional[str] = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self.call_fn(
            messages=messages,
            model=model or self.default_model,
            temperature=temperature,
            response_format=response_format,
        )

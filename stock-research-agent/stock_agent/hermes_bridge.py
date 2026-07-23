"""Bridge between the stock_agent LLMClient interface and hermes internals.

These adapters are only imported when running *inside* hermes. They are kept out
of the core package so standalone/test usage never touches hermes imports.

- ``HermesLLM`` wraps ``agent.auxiliary_client.call_llm`` (a centralized one-shot
  LLM call) so our modules can make model calls with the agent's own provider,
  credentials and model routing.
- ``load_stock_config`` reads the ``stock:`` section from the hermes config.
"""

from __future__ import annotations

import os
from typing import Optional

from .config import StockConfig
from .context import ResearchContext
from .llm import LLMClient


class HermesLLM(LLMClient):
    """LLMClient backed by hermes' ``call_llm`` helper.

    ``fallback_model`` is used when a caller passes ``model=None`` (e.g. the
    strategy compiler with no ``compile_model`` configured).
    """

    def __init__(self, fallback_model: Optional[str] = None, task: Optional[str] = None):
        self.fallback_model = fallback_model
        self.task = task

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.4,
        response_format: Optional[str] = None,
    ) -> str:
        from agent.auxiliary_client import call_llm

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        extra_body = None
        if response_format == "json":
            extra_body = {"response_format": {"type": "json_object"}}
        resp = call_llm(
            task=self.task,
            model=model or self.fallback_model,
            messages=messages,
            temperature=temperature,
            extra_body=extra_body,
        )
        try:
            return resp.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return str(resp)


def load_stock_config() -> StockConfig:
    """Read the ``stock:`` section from hermes config into a StockConfig."""
    try:
        from run_agent import load_config  # type: ignore
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    return StockConfig.from_dict((cfg or {}).get("stock") or {})


def context_path(config: StockConfig, run_id: str) -> str:
    """Absolute path to a run's context.json."""
    return os.path.join(os.path.expanduser(config.workdir), run_id, "context.json")


def load_context(config: StockConfig, run_id: str) -> ResearchContext:
    """Load a run's ResearchContext from disk."""
    return ResearchContext.load(context_path(config, run_id))

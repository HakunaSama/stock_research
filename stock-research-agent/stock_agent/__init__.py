"""Stock research agent — a hermes-agent add-on for market research.

This package implements four modules (strategy hot-plug, K-line fetch stub,
deep-research with judge/retry, and a 6-stage analysis pipeline) on top of the
Nous Research hermes-agent framework.

It is written to run in two modes:

1. **Standalone** — using an injected ``LLMClient`` (e.g. ``FakeLLM`` for tests
   or an OpenAI-compatible client), with no dependency on hermes internals.
2. **Inside hermes** — the modules in ``hermes_tools/`` wrap these functions as
   ``registry.register`` tools; the orchestration lives in the
   ``skills/stock`` SKILL.md files.

See docs/stock-research-agent-design.md for the full design.
"""

from .context import ResearchContext, Query
from .config import StockConfig, ODRConfig, DEFAULT_CONFIG
from .orchestrator import run_pipeline
from .research import build_researcher, run_deep_research
from .odr import OpenDeepResearcher

__all__ = [
    "ResearchContext",
    "Query",
    "StockConfig",
    "ODRConfig",
    "DEFAULT_CONFIG",
    "run_pipeline",
    "build_researcher",
    "run_deep_research",
    "OpenDeepResearcher",
]

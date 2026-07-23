"""Hermes tool wrappers for the stock-research agent.

Each module here registers one tool via ``tools.registry.registry.register`` and
delegates to the pure functions in the ``stock_agent`` package. The tools are
run_id-stateful: they load the run's ``context.json``, mutate one slot, and save.

Tools (all in the ``stock`` toolset):
- ``stock_run_init``   — create a run, return its run_id
- ``strategy_compile`` — compile a raw strategy into the context
- ``deep_research``    — judge/retry research loop -> context
- ``kline_fetch``      — K-line features (placeholder) -> context
- ``analysis_run``     — 6-stage analysis pipeline -> context

To activate:
1. Ensure ``stock-research-agent/`` is on the Python path (or install as a pkg).
2. Copy/symlink these modules into hermes' ``tools/`` dir, or import them in a
   plugin entry point, so ``discover_builtin_tools()`` picks up the
   ``registry.register(...)`` calls at import time.
3. Add the ``stock`` toolset in ``toolsets.py`` (see README).
"""

"""Hermes tool: kline_fetch.

Writes a K-line feature slot into the run's ResearchContext and returns it as
JSON. Pulls real A-share OHLCV via the vendored ``stocksdk`` and extracts six
technical features (``trend / ma_state / key_levels / patterns / volume_state /
indicators``). Degrades gracefully to ``status="placeholder"`` (features null)
when the fetch fails or K-line is disabled; the analysis S2 stage detects the
placeholder and skips technical-detail claims.

Registration follows the hermes pattern (see tools/memory_tool.py):
``registry.register(name, toolset, schema, handler, ...)``.
"""

from __future__ import annotations

import json

from stock_agent.config import StockConfig
from stock_agent.kline import fetch_kline


KLINE_FETCH_SCHEMA = {
    "name": "kline_fetch",
    "description": (
        "Fetch K-line (candlestick) technical features for a symbol and write "
        "them into the run's context. Pulls real A-share OHLCV and extracts "
        "trend / MA / key-levels / patterns / volume / indicators; degrades to "
        "status='placeholder' (features null) when offline or disabled. "
        "Returns JSON: status, symbol, timeframe, range, features, raw_ref."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run identifier from stock_run_init.",
            },
            "symbol": {
                "type": "string",
                "description": "Ticker symbol, e.g. 'AAPL'. Defaults to the run target.",
            },
            "timeframe": {
                "type": "string",
                "description": "Candle timeframe, e.g. '1d', '1h'. Default '1d'.",
            },
            "range": {
                "type": "string",
                "description": "History range, e.g. '6mo', '1y'. Default '6mo'.",
            },
        },
        "required": ["run_id"],
    },
}


def _handle(args, **kw):
    from stock_agent.hermes_bridge import load_stock_config, load_context

    config: StockConfig = load_stock_config()
    ctx = load_context(config, args["run_id"])
    fetch_kline(
        ctx,
        symbol=args.get("symbol", ""),
        timeframe=args.get("timeframe", "1d"),
        range=args.get("range", "6mo"),
        config=config,
    )
    ctx.save(config.workdir)
    return json.dumps(ctx.kline.__dict__, ensure_ascii=False, indent=2)


try:
    from tools.registry import registry

    registry.register(
        name="kline_fetch",
        toolset="stock",
        schema=KLINE_FETCH_SCHEMA,
        handler=_handle,
        emoji="📈",
        description="Fetch K-line technical features from real A-share OHLCV (placeholder fallback when offline).",
    )
except ImportError:
    # Running standalone (outside hermes) — registration is a no-op.
    pass

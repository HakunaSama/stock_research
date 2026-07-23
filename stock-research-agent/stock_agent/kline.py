"""Module 2: K-line fetch — real OHLCV source + feature extraction.

Pulls OHLCV bars from the vendored ``stocksdk`` (free A-share sources: tencent /
eastmoney / sina, auto failover — see ``vendor/NOTICE.md``), runs them through
``kline_features.extract_features`` to fill the six technical-feature fields the
analysis S2 stage reads, persists the raw OHLCV next to the run, and flips the
slot to ``status="ok"``.

Everything degrades gracefully: if the fetch fails (network down, symbol not an
A-share, source changed) or ``config.kline.enabled`` is off, the slot falls back
to ``status="placeholder"`` with every feature ``None`` — exactly the old
behaviour — so NO other module needs to change either way.

Contract (kept stable across the stub->real transition):
    features = {trend, ma_state, key_levels, patterns, volume_state, indicators}

Standalone entry point: ``fetch_kline(ctx, symbol=..., timeframe=..., range=...)``.
Hermes tool wrapper: see ``hermes_tools/stock_kline_tool.py``.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .config import StockConfig, DEFAULT_CONFIG
from .context import ResearchContext, KlineSlot
from .kline_features import extract_features, bars_to_ohlcv


# The six technical-feature fields the analysis S2 stage reads. All null until
# a real OHLCV source + extractor fills them (see docs design §4).
_FEATURE_KEYS = ("trend", "ma_state", "key_levels", "patterns", "volume_state", "indicators")


def placeholder_features() -> Dict[str, Any]:
    """Return the feature dict with every field null (no data yet)."""
    return {key: None for key in _FEATURE_KEYS}


def _ensure_stocksdk_on_path() -> None:
    """Make the vendored ``stocksdk`` importable without installing it.

    ``vendor/`` is a sibling of the ``stock_agent`` package; add it to sys.path
    once so ``import stocksdk`` resolves to the vendored copy.
    """
    vendor = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)


def _fetch_bars(symbol: str, config: StockConfig) -> List[Any]:
    """Pull OHLCV bars via the vendored stocksdk. Raises on failure."""
    _ensure_stocksdk_on_path()
    from stocksdk import StockClient  # vendored; import lazily so the stub path stays dep-free

    kc = config.kline
    client = StockClient(timeout=kc.timeout)
    return client.get_kline(symbol, period=kc.period, count=kc.count, adjust=kc.adjust)


def _persist_ohlcv(ctx: ResearchContext, config: StockConfig, ohlcv: List[Dict[str, Any]]) -> Optional[str]:
    """Write the raw OHLCV JSON next to the run; return its path (or None)."""
    run_dir = ctx.run_dir(config.workdir)
    if not run_dir:
        return None
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, "kline.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ohlcv, fh, ensure_ascii=False)
    return path


def fetch_kline(
    ctx: ResearchContext,
    *,
    symbol: str = "",
    timeframe: str = "1d",
    range: str = "6mo",
    config: StockConfig = DEFAULT_CONFIG,
) -> ResearchContext:
    """Populate ``ctx.kline`` with real features, or a placeholder on failure.

    On success: ``status="ok"``, six features filled from live OHLCV, and
    ``raw_ref`` pointing at the persisted OHLCV JSON. On any failure (disabled,
    network error, non-A-share symbol, empty result) it falls back to the
    placeholder slot so downstream stages degrade gracefully.
    """
    sym = symbol or ctx.query.target

    if not config.kline.enabled:
        ctx.kline = _placeholder_slot(sym, timeframe, range)
        return ctx

    try:
        bars = _fetch_bars(sym, config)
    except Exception as exc:  # network / invalid symbol / source change — degrade
        ctx.kline = _placeholder_slot(sym, timeframe, range, note=f"fetch failed: {exc}")
        return ctx

    if not bars:
        ctx.kline = _placeholder_slot(sym, timeframe, range, note="no bars returned")
        return ctx

    features = extract_features(bars, ma_windows=config.kline.ma_windows)
    raw_ref = None
    try:
        raw_ref = _persist_ohlcv(ctx, config, bars_to_ohlcv(bars))
    except Exception:
        raw_ref = None  # persisting is best-effort; features are what matter

    ctx.kline = KlineSlot(
        status="ok",
        symbol=sym,
        timeframe=config.kline.period,
        range=f"{len(bars)}bars",
        features=features,
        raw_ref=raw_ref,
    )
    return ctx


def _placeholder_slot(symbol: str, timeframe: str, range: str, note: str = "") -> KlineSlot:
    slot = KlineSlot(
        status="placeholder",
        symbol=symbol,
        timeframe=timeframe,
        range=range,
        features=placeholder_features(),
        raw_ref=None,
    )
    return slot

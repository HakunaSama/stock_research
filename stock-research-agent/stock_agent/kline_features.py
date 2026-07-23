"""Turn raw OHLCV bars into the six technical features the analysis stage reads.

The K-line module (``kline.py``) pulls OHLCV bars from the vendored ``stocksdk``
and hands them here. This module is pure-Python (no numpy/pandas) so it stays in
keeping with the project's "stdlib + minimal deps" style.

Output contract — the six ``_FEATURE_KEYS`` the S2 analysis stage consumes::

    trend        {direction, slope_pct, since, detail}
    ma_state     {ma5, ma10, ma20, ma60, alignment, price_vs_ma20}
    key_levels   {support, resistance, recent_high, recent_low, last_close}
    patterns     [ {name, at, detail}, ... ]        # simple candlestick tags
    volume_state {last, avg20, ratio, state}
    indicators   {rsi14, macd:{dif,dea,hist}}

Every value is a plain JSON-serialisable primitive/dict/list so the whole thing
drops straight into ``KlineSlot.features`` and survives ``json.dumps``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# Bars are the vendored ``stocksdk.models.Bar`` dataclass, but we only touch a
# handful of attributes so we keep this loosely typed (``Any``) to avoid a hard
# import dependency here.

_FEATURE_KEYS = ("trend", "ma_state", "key_levels", "patterns", "volume_state", "indicators")


# --------------------------------------------------------------------------- #
# small numeric helpers (no numpy)                                            #
# --------------------------------------------------------------------------- #

def _round(v: Optional[float], nd: int = 2) -> Optional[float]:
    return None if v is None else round(float(v), nd)


def _sma(values: Sequence[float], window: int) -> Optional[float]:
    """Simple moving average of the LAST ``window`` values, or None if short."""
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def _ema_series(values: Sequence[float], window: int) -> List[float]:
    """Exponential moving average series (seeded with the first value)."""
    if not values:
        return []
    k = 2.0 / (window + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI of the last ``period`` deltas."""
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(len(closes) - period, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """Return (dif, dea, hist) at the latest bar, or (None, None, None)."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema_series(dif, signal)
    hist = (dif[-1] - dea[-1]) * 2.0
    return dif[-1], dea[-1], hist


# --------------------------------------------------------------------------- #
# per-feature builders                                                        #
# --------------------------------------------------------------------------- #

def _build_ma_state(closes: List[float], windows: Sequence[int]) -> Dict[str, Any]:
    mas = {f"ma{w}": _round(_sma(closes, w)) for w in windows}
    ordered = [mas[f"ma{w}"] for w in sorted(windows)]
    present = [m for m in ordered if m is not None]
    # Bull alignment = short MA above long MA (ma5>ma10>ma20>ma60); bear = reverse.
    alignment = "mixed"
    if len(present) == len(ordered) and len(present) >= 2:
        if all(present[i] > present[i + 1] for i in range(len(present) - 1)):
            alignment = "bull"      # 多头排列
        elif all(present[i] < present[i + 1] for i in range(len(present) - 1)):
            alignment = "bear"      # 空头排列
    last = closes[-1]
    ma20 = mas.get("ma20")
    price_vs_ma20 = None
    if ma20:
        price_vs_ma20 = "above" if last >= ma20 else "below"
    out: Dict[str, Any] = dict(mas)
    out["alignment"] = alignment
    out["price_vs_ma20"] = price_vs_ma20
    return out


def _build_trend(closes: List[float], lookback: int = 20) -> Dict[str, Any]:
    """Direction from the % change over the lookback window + short-MA slope."""
    n = min(lookback, len(closes) - 1)
    if n <= 0:
        return {"direction": "flat", "slope_pct": 0.0, "since": n, "detail": "数据不足"}
    start = closes[-n - 1]
    end = closes[-1]
    slope_pct = (end - start) / start * 100 if start else 0.0
    if slope_pct >= 3:
        direction, detail = "up", f"近{n}根累计涨 {slope_pct:.1f}%"
    elif slope_pct <= -3:
        direction, detail = "down", f"近{n}根累计跌 {slope_pct:.1f}%"
    else:
        direction, detail = "flat", f"近{n}根震荡（{slope_pct:+.1f}%）"
    return {"direction": direction, "slope_pct": _round(slope_pct), "since": n, "detail": detail}


def _build_key_levels(highs: List[float], lows: List[float], closes: List[float],
                      lookback: int = 60) -> Dict[str, Any]:
    hs = highs[-lookback:]
    ls = lows[-lookback:]
    last = closes[-1]
    recent_high = max(hs) if hs else None
    recent_low = min(ls) if ls else None
    # Resistance = nearest swing high above price; support = nearest below.
    resistance = min((h for h in hs if h > last), default=recent_high)
    support = max((l for l in ls if l < last), default=recent_low)
    return {
        "support": _round(support),
        "resistance": _round(resistance),
        "recent_high": _round(recent_high),
        "recent_low": _round(recent_low),
        "last_close": _round(last),
    }


def _build_volume_state(volumes: List[int]) -> Dict[str, Any]:
    last = volumes[-1] if volumes else 0
    avg20 = _sma([float(v) for v in volumes], 20)
    ratio = (last / avg20) if avg20 else None
    state = "normal"
    if ratio is not None:
        if ratio >= 1.5:
            state = "surge"        # 放量
        elif ratio <= 0.6:
            state = "shrink"       # 缩量
    return {
        "last": last,
        "avg20": int(avg20) if avg20 else None,
        "ratio": _round(ratio),
        "state": state,
    }


def _build_patterns(opens, highs, lows, closes) -> List[Dict[str, Any]]:
    """A few well-known single/two-bar candlestick tags on the latest bars."""
    patterns: List[Dict[str, Any]] = []
    n = len(closes)
    if n < 2:
        return patterns
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c - o)
    rng = h - l
    upper = h - max(o, c)
    lower = min(o, c) - l

    if rng > 0 and body / rng <= 0.1:
        patterns.append({"name": "doji", "at": -1, "detail": "十字星，多空胶着"})
    if rng > 0 and lower >= body * 2 and upper <= body:
        patterns.append({"name": "hammer", "at": -1, "detail": "长下影线（锤子线），下方承接"})
    if rng > 0 and upper >= body * 2 and lower <= body:
        patterns.append({"name": "shooting_star", "at": -1, "detail": "长上影线，上方抛压"})

    po, pc = opens[-2], closes[-2]
    if c > o and pc < po and c >= po and o <= pc:
        patterns.append({"name": "bullish_engulfing", "at": -1, "detail": "阳包阴（看涨吞没）"})
    if c < o and pc > po and o >= pc and c <= po:
        patterns.append({"name": "bearish_engulfing", "at": -1, "detail": "阴包阳（看跌吞没）"})
    return patterns


# --------------------------------------------------------------------------- #
# public entry                                                                #
# --------------------------------------------------------------------------- #

def extract_features(bars: List[Any], ma_windows: Sequence[int] = (5, 10, 20, 60)) -> Dict[str, Any]:
    """Compute the six-feature dict from a list of OHLCV ``Bar`` objects.

    Bars must be time-ascending (stocksdk guarantees this). If the list is
    empty every feature is None (same shape as the placeholder) so callers can
    treat "no data" uniformly.
    """
    if not bars:
        return {key: None for key in _FEATURE_KEYS}

    opens = [float(b.open) for b in bars]
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]
    closes = [float(b.close) for b in bars]
    volumes = [int(b.volume) for b in bars]

    dif, dea, hist = _macd(closes)
    return {
        "trend": _build_trend(closes),
        "ma_state": _build_ma_state(closes, ma_windows),
        "key_levels": _build_key_levels(highs, lows, closes),
        "patterns": _build_patterns(opens, highs, lows, closes),
        "volume_state": _build_volume_state(volumes),
        "indicators": {
            "rsi14": _round(_rsi(closes)),
            "macd": {"dif": _round(dif, 3), "dea": _round(dea, 3), "hist": _round(hist, 3)},
        },
    }


def bars_to_ohlcv(bars: List[Any]) -> List[Dict[str, Any]]:
    """Serialise bars to a compact JSON list for the frontend candlestick chart."""
    return [
        {
            "t": b.datetime.strftime("%Y-%m-%d %H:%M") if b.datetime else "",
            "o": _round(b.open),
            "h": _round(b.high),
            "l": _round(b.low),
            "c": _round(b.close),
            "v": int(b.volume),
        }
        for b in bars
    ]

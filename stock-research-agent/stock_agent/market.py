"""Live market data — real quotes / indices / search / kline / news.

Everything here hits real upstream sources (via the vendored ``stocksdk``:
tencent / eastmoney / sina with automatic failover; news via eastmoney's
public search API). A small in-process TTL cache keeps request fan-out low so
the terminal can poll every few seconds without hammering upstreams.

All functions return plain JSON-serialisable dicts/lists and raise
``MarketError`` on total failure so HTTP layers can map it to 502/503.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .kline_features import bars_to_ohlcv, extract_features

# --------------------------------------------------------------------------- #
# vendored stocksdk import                                                     #
# --------------------------------------------------------------------------- #


def _ensure_stocksdk_on_path() -> None:
    vendor = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)


class MarketError(RuntimeError):
    """All upstream sources failed for this request."""


_client_lock = threading.Lock()
_client: Any = None


def _get_client() -> Any:
    global _client
    with _client_lock:
        if _client is None:
            _ensure_stocksdk_on_path()
            from stocksdk import StockClient

            _client = StockClient(timeout=5.0)
        return _client


# --------------------------------------------------------------------------- #
# tiny TTL cache                                                               #
# --------------------------------------------------------------------------- #

_cache_lock = threading.Lock()
_cache: Dict[Tuple[str, ...], Tuple[float, Any]] = {}


def _cache_get(key: Tuple[str, ...], ttl: float) -> Optional[Any]:
    with _cache_lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit[0]) < ttl:
            return hit[1]
    return None


def _cache_put(key: Tuple[str, ...], value: Any) -> None:
    with _cache_lock:
        # Bound the cache so long-running processes don't grow unbounded.
        if len(_cache) > 512:
            _cache.clear()
        _cache[key] = (time.time(), value)


# --------------------------------------------------------------------------- #
# quotes                                                                       #
# --------------------------------------------------------------------------- #

# 主要指数（腾讯源代码规范）：上证指数 / 深证成指 / 创业板指 / 沪深300
INDEX_SYMBOLS = ["sh000001", "sz399001", "sz399006", "sh000300"]

_QUOTE_TTL = 2.0  # seconds — supports a 3s index ticker without serving stale snapshots


def _quote_to_dict(q: Any) -> Dict[str, Any]:
    return {
        "symbol": q.symbol,
        "code": q.code,
        "name": q.name,
        "price": q.price,
        "prev_close": q.prev_close,
        "open": q.open,
        "high": q.high,
        "low": q.low,
        "volume": q.volume,
        "amount": q.amount,
        "change": q.change,
        "change_pct": q.change_pct,
        "turnover_rate": q.turnover_rate,
        "pe_ttm": q.pe_ttm,
        "pb": q.pb,
        "total_market_cap": q.total_market_cap,
        "float_market_cap": q.float_market_cap,
        "time": q.timestamp.strftime("%Y-%m-%d %H:%M:%S") if q.timestamp else "",
        "source": q.source,
    }


def get_quotes(symbols: List[str]) -> List[Dict[str, Any]]:
    """Batch realtime quotes. Invalid symbols are silently dropped."""
    cleaned = [s.strip() for s in symbols if s and s.strip()]
    if not cleaned:
        return []
    key = ("quotes",) + tuple(sorted(cleaned))
    cached = _cache_get(key, _QUOTE_TTL)
    if cached is not None:
        return cached
    try:
        quotes = _get_client().get_quotes(cleaned)
    except Exception as exc:
        raise MarketError(f"行情源全部失败: {exc}") from exc
    # Preserve the caller's ordering (get_quotes returns a dict keyed by
    # normalized symbol; match by numeric code as a fallback).
    by_code: Dict[str, Any] = {}
    for q in quotes.values():
        by_code[q.symbol] = q
        by_code[q.code] = q
    out = []
    seen = set()
    for s in cleaned:
        q = quotes.get(s) or by_code.get(s) or by_code.get(re.sub(r"\D", "", s))
        if q is not None and id(q) not in seen:
            seen.add(id(q))
            out.append(_quote_to_dict(q))
    _cache_put(key, out)
    return out


def get_indices() -> List[Dict[str, Any]]:
    """主要大盘指数实时行情（上证指数/深证成指/创业板指/沪深300）。"""
    return get_quotes(INDEX_SYMBOLS)


# --------------------------------------------------------------------------- #
# search                                                                       #
# --------------------------------------------------------------------------- #

_SEARCH_TTL = 300.0


def search(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """代码/名称/拼音首字母搜索沪深京 A 股。"""
    kw = keyword.strip()
    if not kw:
        return []
    key = ("search", kw.lower())
    cached = _cache_get(key, _SEARCH_TTL)
    if cached is None:
        try:
            results = _get_client().search(kw)
        except Exception as exc:
            raise MarketError(f"搜索源全部失败: {exc}") from exc
        cached = [
            {
                "symbol": r.symbol,
                "code": r.code,
                "name": r.name,
                "market": r.market,
                "type": r.security_type,
            }
            for r in results
            # 只保留 A 股股票（GP-A / GP-A-KCB / GP-A-CYB 等），过滤指数/基金/债券
            if str(r.security_type).upper().startswith("GP")
        ]
        _cache_put(key, cached)
    return cached[:limit]


# --------------------------------------------------------------------------- #
# live kline (any symbol, not tied to a research run)                          #
# --------------------------------------------------------------------------- #

_KLINE_TTL = {"1m": 30.0, "5m": 60.0, "15m": 60.0, "30m": 120.0, "60m": 120.0,
              "day": 300.0, "week": 3600.0, "month": 3600.0}

_ALLOWED_PERIODS = set(_KLINE_TTL)


def get_live_kline(symbol: str, period: str = "day", count: int = 180) -> Dict[str, Any]:
    """Realtime OHLCV bars + computed technical features for ANY A-share symbol."""
    if period not in _ALLOWED_PERIODS:
        raise ValueError(f"period 必须是 {sorted(_ALLOWED_PERIODS)} 之一")
    count = max(30, min(int(count), 500))
    key = ("kline", symbol, period, str(count))
    cached = _cache_get(key, _KLINE_TTL[period])
    if cached is not None:
        return cached
    try:
        bars = _get_client().get_kline(symbol, period=period, count=count, adjust="qfq")
    except Exception as exc:
        raise MarketError(f"K线源全部失败: {exc}") from exc
    payload = {
        "status": "ok" if bars else "error",
        "symbol": symbol,
        "timeframe": period,
        "range": f"{len(bars)}bars",
        "bars": bars_to_ohlcv(bars),
        # 特征提取为纯本地计算；分钟线同样适用（趋势/均线/量能等口径一致）
        "features": extract_features(bars) if bars else None,
    }
    _cache_put(key, payload)
    return payload


# --------------------------------------------------------------------------- #
# market rankings (eastmoney push2 clist API — whole-market realtime board)    #
# --------------------------------------------------------------------------- #

_RANK_TTL = 10.0

# kind -> (排序字段, 是否降序)。f3 涨跌幅 / f6 成交额 / f8 换手率
_RANK_KINDS = {
    "pct_desc": ("f3", True),   # 涨幅榜
    "pct_asc": ("f3", False),   # 跌幅榜
    "amount": ("f6", True),     # 成交额榜
    "turnover": ("f8", True),   # 换手率榜
}


def get_rank(kind: str = "pct_desc", limit: int = 30) -> List[Dict[str, Any]]:
    """全市场实时榜单（沪深 A 股），来自东方财富公开行情列表接口。"""
    if kind not in _RANK_KINDS:
        raise ValueError(f"kind 必须是 {sorted(_RANK_KINDS)} 之一")
    limit = max(5, min(int(limit), 100))
    key = ("rank", kind, str(limit))
    cached = _cache_get(key, _RANK_TTL)
    if cached is not None:
        return cached

    import requests

    fid, desc = _RANK_KINDS[kind]
    params = {
        "pn": 1,
        "pz": limit,
        "po": 1 if desc else 0,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": fid,
        # 沪深 A 股（含科创/创业板），不含北交所指数基金等
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
        "fields": "f2,f3,f5,f6,f8,f12,f14,f20",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    diff: List[Dict[str, Any]] = []
    errors: List[str] = []
    # 主站偶发拒连；delay 镜像稳定（数据延迟秒级，对榜单足够）
    for host in ("push2.eastmoney.com", "push2delay.eastmoney.com"):
        try:
            resp = requests.get(
                f"https://{host}/api/qt/clist/get",
                params=params, headers=headers, timeout=6,
            )
            resp.raise_for_status()
            diff = ((resp.json().get("data") or {}).get("diff")) or []
            if diff:
                break
        except Exception as exc:
            errors.append(f"{host}: {exc}")
    if not diff:
        raise MarketError("榜单源失败: " + ("; ".join(errors) or "空数据"))

    out: List[Dict[str, Any]] = []
    for row in diff:
        code = str(row.get("f12") or "")
        name = str(row.get("f14") or "")
        if not code or not name:
            continue

        def _num(v: Any) -> Optional[float]:
            return v if isinstance(v, (int, float)) else None  # "-" 表示停牌/无数据

        out.append(
            {
                "code": code,
                "name": name,
                "price": _num(row.get("f2")),
                "change_pct": _num(row.get("f3")),
                "volume": _num(row.get("f5")),        # 手
                "amount": _num(row.get("f6")),        # 元
                "turnover_rate": _num(row.get("f8")), # %
                "total_market_cap": _num(row.get("f20")),
            }
        )
    _cache_put(key, out)
    return out


# --------------------------------------------------------------------------- #
# per-stock news (eastmoney public search API — same endpoint akshare uses)    #
# --------------------------------------------------------------------------- #

_NEWS_TTL = 300.0
_TAG_RE = re.compile(r"</?em>|<[^>]+>")


def get_news(keyword: str, limit: int = 12) -> List[Dict[str, Any]]:
    """个股相关资讯（东方财富公开搜索接口，按相关度+时间排序）。

    ``keyword`` 用股票代码即可（东财按代码召回该股新闻）；失败返回 []
    而不是抛错 —— 新闻属于增强信息，不应阻塞行情主链路。
    """
    kw = keyword.strip()
    if not kw:
        return []
    key = ("news", kw, str(limit))
    cached = _cache_get(key, _NEWS_TTL)
    if cached is not None:
        return cached

    import requests

    param = {
        "uid": "",
        "keyword": kw,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "time",
                "pageIndex": 1,
                "pageSize": limit,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    out: List[Dict[str, Any]] = []
    try:
        resp = requests.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params={"cb": "cb", "param": json.dumps(param, ensure_ascii=False)},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=6,
        )
        resp.raise_for_status()
        text = resp.text
        body = text[text.index("(") + 1 : text.rindex(")")]
        data = json.loads(body)
        articles = (data.get("result") or {}).get("cmsArticleWebOld") or []
        for a in articles:
            title = _TAG_RE.sub("", str(a.get("title") or "")).strip()
            if not title:
                continue
            out.append(
                {
                    "title": title,
                    "summary": _TAG_RE.sub("", str(a.get("content") or "")).strip(),
                    "source": str(a.get("mediaName") or ""),
                    "date": str(a.get("date") or ""),
                    "url": str(a.get("url") or ""),
                }
            )
    except Exception:
        return []  # 新闻降级为空，不影响行情
    _cache_put(key, out)
    return out

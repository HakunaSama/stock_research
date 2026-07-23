"""腾讯行情数据源（主数据源）。

- 实时行情: https://qt.gtimg.cn/q=sh600519,sz000001    （GBK 编码，字段以 ~ 分隔）
- 日/周/月K: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
- 分钟K:     https://ifzq.gtimg.cn/appstock/app/kline/mkline
- 搜索:      https://smartbox.gtimg.cn/s3/

免费、无需鉴权，支持沪深京股票、指数、基金。
"""
import codecs
import re
from datetime import datetime
from typing import Dict, List
from urllib.parse import quote as urlquote

from ..exceptions import DataSourceError
from ..models import Bar, OrderLevel, Quote, SearchResult
from ..symbols import MARKETS
from .base import DataSource, opt_float, to_float, to_int

_QUOTE_URL = "https://qt.gtimg.cn/q={symbols}"
_KLINE_URL = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    "?param={symbol},{period},,,{count},{fq}"
)
_MKLINE_URL = (
    "https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={symbol},{period},,{count}"
)
_SEARCH_URL = "https://smartbox.gtimg.cn/s3/?v=2&q={keyword}&t=all"

_LINE_RE = re.compile(r'v_(\w+)="(.*?)"')
_BATCH_SIZE = 60


def _parse_dt(raw: str) -> datetime:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 14:
        return datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
    if len(digits) >= 12:
        return datetime.strptime(digits[:12], "%Y%m%d%H%M")
    if len(digits) >= 8:
        return datetime.strptime(digits[:8], "%Y%m%d")
    return datetime.now()


class TencentSource(DataSource):
    name = "tencent"
    supports_quotes = True
    supports_kline = True
    supports_search = True

    # ---------- 实时行情 ----------

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        result: Dict[str, Quote] = {}
        for i in range(0, len(symbols), _BATCH_SIZE):
            chunk = symbols[i : i + _BATCH_SIZE]
            url = _QUOTE_URL.format(symbols=",".join(chunk))
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
            except Exception as e:
                raise DataSourceError(self.name, f"行情请求失败: {e}")
            resp.encoding = "gbk"
            for symbol, payload in _LINE_RE.findall(resp.text):
                if symbol not in chunk:
                    continue  # 跳过 v_pv_none_match 之类的噪声键
                quote = self._parse_quote(symbol, payload)
                if quote is not None:
                    result[symbol] = quote
        return result

    def _parse_quote(self, symbol: str, payload: str):
        f = payload.split("~")
        if len(f) < 38 or not f[1]:
            return None
        bids = [
            OrderLevel(price=to_float(f[9 + i * 2]), volume=to_int(f[10 + i * 2]) * 100)
            for i in range(5)
        ]
        asks = [
            OrderLevel(price=to_float(f[19 + i * 2]), volume=to_int(f[20 + i * 2]) * 100)
            for i in range(5)
        ]
        # 字段35 形如 "最新价/成交量(手)/成交额(元)"，取精确到元的成交额
        amount = 0.0
        parts = f[35].split("/")
        if len(parts) == 3:
            amount = to_float(parts[2])
        if amount == 0.0:
            amount = to_float(f[37]) * 1e4  # 万元兜底

        def cap(idx):
            v = opt_float(f[idx]) if len(f) > idx else None
            return v * 1e8 if v else None  # 亿元 -> 元

        return Quote(
            symbol=symbol,
            code=f[2],
            name=f[1],
            price=to_float(f[3]),
            prev_close=to_float(f[4]),
            open=to_float(f[5]),
            high=to_float(f[33]),
            low=to_float(f[34]),
            volume=to_int(f[6]) * 100,  # 手 -> 股
            amount=amount,
            change=to_float(f[31]),
            change_pct=to_float(f[32]),
            timestamp=_parse_dt(f[30]),
            source=self.name,
            bids=[b for b in bids if b.price > 0],
            asks=[a for a in asks if a.price > 0],
            turnover_rate=opt_float(f[38]),
            pe_ttm=opt_float(f[39]) if len(f) > 39 else None,
            pb=opt_float(f[46]) if len(f) > 46 else None,
            float_market_cap=cap(44),
            total_market_cap=cap(45),
        )

    # ---------- K 线 ----------

    def get_kline(self, symbol: str, period: str, count: int, adjust: str) -> List[Bar]:
        if period.endswith("m"):
            return self._get_minute_kline(symbol, period, count)
        fq = "" if adjust == "none" else adjust
        url = _KLINE_URL.format(symbol=symbol, period=period, count=count, fq=fq)
        data = self._fetch_kline_json(url, symbol)
        # 复权数据键形如 "qfqday"；不复权或指数（无复权概念）时是 "day"
        rows = data.get(fq + period) or data.get(period) or []
        bars = [self._parse_bar(row) for row in rows if isinstance(row, list)]
        return bars[-count:]  # 腾讯会在 count 根历史之外额外附带当日一根

    def _get_minute_kline(self, symbol: str, period: str, count: int) -> List[Bar]:
        key = "m" + period[:-1]  # "5m" -> "m5"
        url = _MKLINE_URL.format(symbol=symbol, period=key, count=count)
        data = self._fetch_kline_json(url, symbol)
        rows = data.get(key) or []
        return [self._parse_bar(row) for row in rows if isinstance(row, list)]

    def _fetch_kline_json(self, url: str, symbol: str) -> dict:
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            raise DataSourceError(self.name, f"K线请求失败: {e}")
        if body.get("code") != 0:
            raise DataSourceError(self.name, f"K线接口返回错误: {body.get('msg')}")
        return (body.get("data") or {}).get(symbol) or {}

    @staticmethod
    def _parse_bar(row: list) -> Bar:
        return Bar(
            datetime=_parse_dt(str(row[0])),
            open=to_float(row[1]),
            close=to_float(row[2]),
            high=to_float(row[3]),
            low=to_float(row[4]),
            volume=to_int(row[5]) * 100,  # 手 -> 股
        )

    # ---------- 搜索 ----------

    def search(self, keyword: str) -> List[SearchResult]:
        url = _SEARCH_URL.format(keyword=urlquote(keyword.encode("utf-8")))
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as e:
            raise DataSourceError(self.name, f"搜索请求失败: {e}")
        m = re.search(r'v_hint="(.*?)"', resp.text)
        if not m or m.group(1) in ("", "N;"):
            return []
        results = []
        for entry in m.group(1).split("^"):
            parts = entry.split("~")
            if len(parts) < 5:
                continue
            market, code, raw_name, _pinyin, sec_type = parts[:5]
            if market not in MARKETS:
                continue  # 过滤掉港股/美股等
            try:
                name = codecs.decode(raw_name, "unicode_escape")
            except Exception:
                name = raw_name
            results.append(
                SearchResult(
                    symbol=market + code,
                    code=code,
                    name=name,
                    market=market,
                    security_type=sec_type,
                )
            )
        return results

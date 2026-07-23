"""东方财富行情数据源（备用，实时行情 + K 线）。

- 批量行情: https://push2.eastmoney.com/api/qt/ulist.np/get （含编号集群节点轮询）
- K 线:     https://push2his.eastmoney.com/api/qt/stock/kline/get

secid 规则：沪市 = "1.代码"，深市/北交所 = "0.代码"。
"""
import time
from datetime import datetime
from typing import Dict, List

import requests

from ..exceptions import DataSourceError
from ..models import Bar, Quote
from ..symbols import split
from .base import DataSource, opt_float, to_float, to_int

# 东财是集群部署，主域名被限流/断连时可切换到编号节点
_QUOTE_HOSTS = (
    "push2.eastmoney.com",
    "1.push2.eastmoney.com",
    "33.push2.eastmoney.com",
    "82.push2.eastmoney.com",
)
_KLINE_HOSTS = (
    "push2his.eastmoney.com",
    "1.push2his.eastmoney.com",
    "33.push2his.eastmoney.com",
)
_QUOTE_PATH = "/api/qt/ulist.np/get"
_KLINE_PATH = "/api/qt/stock/kline/get"

_QUOTE_FIELDS = (
    "f2,f3,f4,f5,f6,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f115,f124"
)
_KLT = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "day": 101, "week": 102, "month": 103}
_FQT = {"none": 0, "qfq": 1, "hfq": 2}
_BATCH_SIZE = 100


def _secid(symbol: str) -> str:
    market, code = split(symbol)
    return ("1." if market == "sh" else "0.") + code


class EastmoneySource(DataSource):
    name = "eastmoney"
    supports_quotes = True
    supports_kline = True

    def _get_json(self, hosts: tuple, path: str, params: dict, what: str) -> dict:
        """依次尝试集群各节点，直到拿到 JSON。

        主域名可能对单 IP 临时限流（表现为连接被服务端直接断开），
        编号节点通常仍然可用，因此逐个切换而不是原地重试。
        """
        last_error = None
        for host in hosts:
            for _attempt in range(2):  # 限流是按连接随机掐的，原地重试一次也有意义
                try:
                    resp = self.session.get(
                        f"https://{host}{path}", params=params, timeout=self.timeout
                    )
                    resp.raise_for_status()
                    return resp.json()
                except requests.exceptions.RequestException as e:
                    last_error = e
                except ValueError as e:  # JSON 解析失败
                    last_error = e
                time.sleep(0.2)
        raise DataSourceError(self.name, f"{what}请求失败（已尝试 {len(hosts)} 个节点）: {last_error}")

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        # secid 到归一化代码的反查表（sh/sz 用市场号区分，bj 与 sz 共用 0，靠代码本身不重叠区分）
        secid_map = {_secid(s): s for s in symbols}
        result: Dict[str, Quote] = {}
        secids = list(secid_map)
        for i in range(0, len(secids), _BATCH_SIZE):
            chunk = secids[i : i + _BATCH_SIZE]
            params = {
                "fltt": "2",
                "invt": "2",
                "secids": ",".join(chunk),
                "fields": _QUOTE_FIELDS,
            }
            body = self._get_json(_QUOTE_HOSTS, _QUOTE_PATH, params, "行情")
            for item in ((body.get("data") or {}).get("diff") or []):
                key = f"{item.get('f13')}.{item.get('f12')}"
                symbol = secid_map.get(key)
                if symbol is None:
                    continue
                quote = self._parse_quote(symbol, item)
                if quote is not None:
                    result[symbol] = quote
        return result

    def _parse_quote(self, symbol: str, d: dict):
        if not d.get("f14"):
            return None
        ts = d.get("f124")
        return Quote(
            symbol=symbol,
            code=str(d.get("f12", symbol[2:])),
            name=d["f14"],
            price=to_float(d.get("f2")),  # 停牌时东财返回 "-"，落为 0
            prev_close=to_float(d.get("f18")),
            open=to_float(d.get("f17")),
            high=to_float(d.get("f15")),
            low=to_float(d.get("f16")),
            volume=to_int(d.get("f5")) * 100,  # 手 -> 股
            amount=to_float(d.get("f6")),
            change=to_float(d.get("f4")),
            change_pct=to_float(d.get("f3")),
            timestamp=datetime.fromtimestamp(ts) if isinstance(ts, (int, float)) else datetime.now(),
            source=self.name,
            turnover_rate=opt_float(d.get("f8")),
            pe_ttm=opt_float(d.get("f115")),
            pb=opt_float(d.get("f23")),
            total_market_cap=opt_float(d.get("f20")),
            float_market_cap=opt_float(d.get("f21")),
        )

    def get_kline(self, symbol: str, period: str, count: int, adjust: str) -> List[Bar]:
        params = {
            "secid": _secid(symbol),
            "klt": str(_KLT[period]),
            "fqt": str(_FQT[adjust]),
            "lmt": str(count),
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
        body = self._get_json(_KLINE_HOSTS, _KLINE_PATH, params, "K线")
        klines = ((body.get("data") or {}).get("klines")) or []
        bars = []
        for line in klines:
            # "2026-07-22,开,收,高,低,量(手),额(元)" 分钟线日期带 HH:MM
            f = line.split(",")
            if len(f) < 7:
                continue
            try:
                dt = datetime.strptime(f[0], "%Y-%m-%d %H:%M" if " " in f[0] else "%Y-%m-%d")
            except ValueError:
                continue
            bars.append(
                Bar(
                    datetime=dt,
                    open=to_float(f[1]),
                    close=to_float(f[2]),
                    high=to_float(f[3]),
                    low=to_float(f[4]),
                    volume=to_int(f[5]) * 100,
                    amount=to_float(f[6]),
                )
            )
        return bars

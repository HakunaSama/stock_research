"""新浪行情数据源（备用，仅实时行情）。

https://hq.sinajs.cn/list=sh600519,sz000001 （GBK 编码，必须带 Referer 头）

注意：新浪对北交所代码的数据更新不及时，客户端默认把它排在腾讯之后。
"""
import re
from datetime import datetime
from typing import Dict, List

from ..exceptions import DataSourceError
from ..models import OrderLevel, Quote
from .base import DataSource, to_float, to_int

_QUOTE_URL = "https://hq.sinajs.cn/list={symbols}"
_LINE_RE = re.compile(r'var hq_str_(\w+)="(.*?)"')
_BATCH_SIZE = 60


class SinaSource(DataSource):
    name = "sina"
    supports_quotes = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers["Referer"] = "https://finance.sina.com.cn"

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
                quote = self._parse_quote(symbol, payload)
                if quote is not None:
                    result[symbol] = quote
        return result

    def _parse_quote(self, symbol: str, payload: str):
        f = payload.split(",")
        if len(f) < 32 or not f[0]:
            return None
        price = to_float(f[3])
        prev_close = to_float(f[2])
        change = price - prev_close if price > 0 else 0.0
        change_pct = change / prev_close * 100 if prev_close > 0 else 0.0
        # 10~19: 买一~买五 (量,价)；20~29: 卖一~卖五 (量,价)，量单位是股
        bids = [
            OrderLevel(price=to_float(f[11 + i * 2]), volume=to_int(f[10 + i * 2]))
            for i in range(5)
        ]
        asks = [
            OrderLevel(price=to_float(f[21 + i * 2]), volume=to_int(f[20 + i * 2]))
            for i in range(5)
        ]
        try:
            ts = datetime.strptime(f"{f[30]} {f[31]}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts = datetime.now()
        return Quote(
            symbol=symbol,
            code=symbol[2:],
            name=f[0],
            price=price,
            prev_close=prev_close,
            open=to_float(f[1]),
            high=to_float(f[4]),
            low=to_float(f[5]),
            volume=to_int(f[8]),  # 新浪本身就是股
            amount=to_float(f[9]),
            change=round(change, 4),
            change_pct=round(change_pct, 2),
            timestamp=ts,
            source=self.name,
            bids=[b for b in bids if b.price > 0],
            asks=[a for a in asks if a.price > 0],
        )

"""SDK 对外门面：StockClient。

对每类请求按数据源优先级依次尝试，前一个失败自动切换下一个（故障转移），
全部失败才抛 AllSourcesFailedError。
"""
import logging
from typing import Dict, Iterable, List, Optional

import requests

from .exceptions import (
    AllSourcesFailedError,
    DataSourceError,
    StockSDKError,
    SymbolNotFoundError,
)
from .models import Bar, Quote, SearchResult
from .sources import DataSource, EastmoneySource, SinaSource, TencentSource
from .sources.base import ADJUSTS, PERIODS
from .symbols import normalize

logger = logging.getLogger("stocksdk")


class StockClient:
    """A 股实时行情客户端。

    用法::

        from stocksdk import StockClient

        client = StockClient()
        quote = client.get_quote("600519")
        print(quote.name, quote.price, quote.change_pct)

    参数:
        sources: 自定义数据源实例列表（按优先级排序）。默认腾讯 -> 东财 -> 新浪。
        timeout: 每个 HTTP 请求的超时秒数。
    """

    def __init__(
        self,
        sources: Optional[List[DataSource]] = None,
        timeout: float = 5.0,
        session: Optional[requests.Session] = None,
    ):
        if sources is None:
            # 腾讯字段最全且北交所数据最新；东财次之；新浪的北交所数据滞后放最后
            sources = [
                TencentSource(timeout=timeout, session=session),
                EastmoneySource(timeout=timeout, session=session),
                SinaSource(timeout=timeout, session=session),
            ]
        self.sources = sources

    # ---------- 实时行情 ----------

    def get_quote(self, symbol: str) -> Quote:
        """查询单只证券的实时行情。

        symbol 支持 "600519"、"sh600519"、"600519.SH"；
        指数请显式带前缀，如 "sh000001"（上证指数）。
        """
        normalized = normalize(symbol)
        quotes = self.get_quotes([normalized])
        if normalized not in quotes:
            raise SymbolNotFoundError(f"未查询到 {symbol!r}（归一化为 {normalized!r}）的行情")
        return quotes[normalized]

    def get_quotes(self, symbols: Iterable[str]) -> Dict[str, Quote]:
        """批量查询实时行情，返回 {归一化代码: Quote}。

        无效代码不会出现在返回值中；有代码缺失时会自动尝试下一个数据源补齐。
        """
        remaining = list(dict.fromkeys(normalize(s) for s in symbols))
        if not remaining:
            return {}
        capable = self._capable("supports_quotes")
        if not capable:
            raise AllSourcesFailedError([DataSourceError("client", "没有支持实时行情的数据源")])
        result: Dict[str, Quote] = {}
        errors: List[Exception] = []
        for source in capable:
            try:
                got = source.get_quotes(remaining)
            except StockSDKError as e:
                logger.warning("数据源 %s 拉取行情失败，切换下一个: %s", source.name, e)
                errors.append(e)
                continue
            result.update(got)
            remaining = [s for s in remaining if s not in result]
            if not remaining:
                return result
        if result or len(errors) < len(capable):
            # 至少有一个源正常响应：剩余未返回的代码视为无效，由调用方决定如何处理
            return result
        raise AllSourcesFailedError(errors)

    # ---------- K 线 ----------

    def get_kline(
        self,
        symbol: str,
        period: str = "day",
        count: int = 100,
        adjust: str = "qfq",
    ) -> List[Bar]:
        """查询 K 线，按时间升序返回。

        参数:
            period: "1m" / "5m" / "15m" / "30m" / "60m" / "day" / "week" / "month"
            count: 返回最近多少根
            adjust: "qfq" 前复权 / "hfq" 后复权 / "none" 不复权（分钟线固定不复权）
        """
        if period not in PERIODS:
            raise ValueError(f"period 必须是 {PERIODS} 之一，收到 {period!r}")
        if adjust not in ADJUSTS:
            raise ValueError(f"adjust 必须是 {ADJUSTS} 之一，收到 {adjust!r}")
        normalized = normalize(symbol)
        errors: List[Exception] = []
        for source in self._capable("supports_kline"):
            try:
                bars = source.get_kline(normalized, period, count, adjust)
            except StockSDKError as e:
                logger.warning("数据源 %s 拉取K线失败，切换下一个: %s", source.name, e)
                errors.append(e)
                continue
            if bars:
                return bars[-count:]
        if errors:
            raise AllSourcesFailedError(errors)
        return []

    # ---------- 搜索 ----------

    def search(self, keyword: str) -> List[SearchResult]:
        """按代码/名称/拼音首字母搜索沪深京证券，如 search("茅台")、search("gzmt")。"""
        errors: List[Exception] = []
        for source in self._capable("supports_search"):
            try:
                return source.search(keyword)
            except StockSDKError as e:
                logger.warning("数据源 %s 搜索失败，切换下一个: %s", source.name, e)
                errors.append(e)
        raise AllSourcesFailedError(errors or [DataSourceError("client", "没有支持搜索的数据源")])

    def _capable(self, capability: str) -> List[DataSource]:
        return [s for s in self.sources if getattr(s, capability, False)]

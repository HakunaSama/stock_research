"""stocksdk: A 股实时行情 SDK（免费数据源：腾讯 / 东方财富 / 新浪）。

快速上手::

    from stocksdk import StockClient

    client = StockClient()
    quote = client.get_quote("600519")          # 实时行情
    quotes = client.get_quotes(["600519", "000001.SZ", "sh000001"])  # 批量
    bars = client.get_kline("600519", period="day", count=30)        # K线
    hits = client.search("茅台")                 # 搜索
"""
from .client import StockClient
from .exceptions import (
    AllSourcesFailedError,
    DataSourceError,
    InvalidSymbolError,
    StockSDKError,
    SymbolNotFoundError,
)
from .models import Bar, OrderLevel, Quote, SearchResult
from .sources import EastmoneySource, SinaSource, TencentSource
from .symbols import normalize

__version__ = "0.1.0"

__all__ = [
    "StockClient",
    "Quote",
    "Bar",
    "OrderLevel",
    "SearchResult",
    "normalize",
    "TencentSource",
    "SinaSource",
    "EastmoneySource",
    "StockSDKError",
    "InvalidSymbolError",
    "DataSourceError",
    "SymbolNotFoundError",
    "AllSourcesFailedError",
]

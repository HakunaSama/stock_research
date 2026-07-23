"""数据源抽象基类。"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import requests

from ..models import Bar, Quote, SearchResult

# K 线周期：分钟线 + 日/周/月
PERIODS = ("1m", "5m", "15m", "30m", "60m", "day", "week", "month")
# 复权方式：前复权 / 后复权 / 不复权（分钟线不支持复权）
ADJUSTS = ("qfq", "hfq", "none")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class DataSource(ABC):
    """一个行情数据源。子类按能力实现对应方法，不支持的能力保持默认 False。"""

    name: str = "base"
    supports_quotes: bool = False
    supports_kline: bool = False
    supports_search: bool = False

    def __init__(self, timeout: float = 5.0, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", _UA)

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """批量拉取实时行情。symbols 为归一化代码列表，返回 {symbol: Quote}。

        数据源没有返回的代码不会出现在结果里（由上层决定如何处理）。
        """
        raise NotImplementedError(f"{self.name} 不支持实时行情")

    def get_kline(self, symbol: str, period: str, count: int, adjust: str) -> List[Bar]:
        """拉取 K 线，按时间升序返回。"""
        raise NotImplementedError(f"{self.name} 不支持 K 线")

    def search(self, keyword: str) -> List[SearchResult]:
        """按代码/名称/拼音搜索 A 股证券。"""
        raise NotImplementedError(f"{self.name} 不支持搜索")


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def opt_float(value) -> Optional[float]:
    """解析可选字段，'-'、空串、None 都归为 None。"""
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

"""对外暴露的数据模型。

单位约定（全 SDK 统一）：
- 价格/金额：元
- 成交量：股（不是手）
- 市值：元
- 百分比字段（涨跌幅、换手率等）：百分数数值，如 -1.13 表示 -1.13%
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class OrderLevel:
    """盘口挡位。"""

    price: float
    volume: int  # 股


@dataclass
class Quote:
    """一只证券的实时快照行情。"""

    symbol: str  # 归一化代码，如 "sh600519"
    code: str  # 纯数字代码，如 "600519"
    name: str
    price: float  # 最新价
    prev_close: float
    open: float
    high: float
    low: float
    volume: int  # 成交量（股）
    amount: float  # 成交额（元）
    change: float  # 涨跌额（元）
    change_pct: float  # 涨跌幅（%）
    timestamp: datetime  # 行情时间（交易所时间）
    source: str  # 本条数据来自哪个数据源
    bids: List[OrderLevel] = field(default_factory=list)  # 买一~买五
    asks: List[OrderLevel] = field(default_factory=list)  # 卖一~卖五
    turnover_rate: Optional[float] = None  # 换手率（%）
    pe_ttm: Optional[float] = None  # 市盈率 TTM
    pb: Optional[float] = None  # 市净率
    total_market_cap: Optional[float] = None  # 总市值（元）
    float_market_cap: Optional[float] = None  # 流通市值（元）

    @property
    def is_suspended(self) -> bool:
        """是否疑似停牌（无成交且价格为 0）。"""
        return self.volume == 0 and self.price == 0


@dataclass
class Bar:
    """一根 K 线。"""

    datetime: datetime  # 日线及以上为当日 00:00，分钟线为该分钟
    open: float
    close: float
    high: float
    low: float
    volume: int  # 股
    amount: Optional[float] = None  # 成交额（元），部分数据源不提供


@dataclass
class SearchResult:
    """按关键字搜索证券的结果。"""

    symbol: str  # 归一化代码，如 "sh600519"
    code: str
    name: str
    market: str  # "sh" / "sz" / "bj"
    security_type: str  # 数据源返回的类型标记，如 "GP-A"（A股）、"ZS"（指数）

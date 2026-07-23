"""SDK 异常体系。"""


class StockSDKError(Exception):
    """所有 SDK 异常的基类。"""


class InvalidSymbolError(StockSDKError):
    """股票代码无法识别或格式非法。"""


class DataSourceError(StockSDKError):
    """单个数据源请求或解析失败。"""

    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"[{source}] {message}")


class SymbolNotFoundError(StockSDKError):
    """数据源没有返回该代码的数据（代码不存在或已退市）。"""


class AllSourcesFailedError(StockSDKError):
    """所有数据源都失败时抛出，携带每个源的错误详情。"""

    def __init__(self, errors):
        self.errors = list(errors)
        detail = "; ".join(str(e) for e in self.errors)
        super().__init__(f"所有数据源均失败: {detail}")

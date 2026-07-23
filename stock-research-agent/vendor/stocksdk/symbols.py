"""证券代码归一化。

统一内部表示为小写 "sh600519" / "sz000001" / "bj430047"。

支持的输入格式：
- "600519"（6 位纯数字，自动推断交易所）
- "sh600519" / "SH600519"
- "600519.SH" / "600519.sh"
- "sh000001"（指数必须带交易所前缀，因为 000001 同时是平安银行和上证指数）
"""
import re
from typing import Tuple

from .exceptions import InvalidSymbolError

MARKETS = ("sh", "sz", "bj")

_PREFIXED = re.compile(r"^(sh|sz|bj)(\d{6})$", re.IGNORECASE)
_SUFFIXED = re.compile(r"^(\d{6})\.(sh|sz|bj)$", re.IGNORECASE)
_BARE = re.compile(r"^\d{6}$")


def _infer_market(code: str) -> str:
    """根据 6 位代码首位推断交易所（仅针对股票/基金，指数请显式加前缀）。"""
    head1, head2 = code[0], code[:2]
    if head1 in ("4", "8") or head2 == "92":  # 43/83/87/92 北交所（92 要先于沪市 9 判断）
        return "bj"
    if head1 in ("6", "9", "5"):  # 60/68 沪A、900 沪B、5 沪基金
        return "sh"
    if head1 in ("0", "3", "2", "1"):  # 00 深A、30 创业板、200 深B、1 深基金
        return "sz"
    raise InvalidSymbolError(f"无法从代码 {code!r} 推断交易所，请使用 sh/sz/bj 前缀显式指定")


def normalize(symbol: str) -> str:
    """把任意支持的格式归一化为 'sh600519' 形式。

    >>> normalize("600519")
    'sh600519'
    >>> normalize("000001.SZ")
    'sz000001'
    """
    s = str(symbol).strip()
    m = _PREFIXED.match(s)
    if m:
        return m.group(1).lower() + m.group(2)
    m = _SUFFIXED.match(s)
    if m:
        return m.group(2).lower() + m.group(1)
    if _BARE.match(s):
        return _infer_market(s) + s
    raise InvalidSymbolError(
        f"无法识别的证券代码: {symbol!r}（支持 '600519'、'sh600519'、'600519.SH' 格式）"
    )


def split(normalized: str) -> Tuple[str, str]:
    """把 'sh600519' 拆成 ('sh', '600519')。"""
    return normalized[:2], normalized[2:]

"""命令行入口。

用法:
    python -m stocksdk quote 600519 000001.SZ sh000001
    python -m stocksdk kline 600519 --period day --count 10 --adjust qfq
    python -m stocksdk search 茅台
"""
import argparse
import sys

from .client import StockClient
from .sources.base import ADJUSTS, PERIODS


def _cmd_quote(client: StockClient, args) -> None:
    quotes = client.get_quotes(args.symbols)
    fmt = "{:<10} {:<10} {:>10} {:>8} {:>8} {:>14} {:>16}  {}"
    print(fmt.format("代码", "名称", "最新价", "涨跌", "涨跌幅%", "成交量(股)", "成交额(元)", "时间"))
    for symbol, q in quotes.items():
        print(
            fmt.format(
                symbol,
                q.name,
                f"{q.price:.2f}",
                f"{q.change:+.2f}",
                f"{q.change_pct:+.2f}",
                f"{q.volume:,}",
                f"{q.amount:,.0f}",
                q.timestamp.strftime("%H:%M:%S"),
            )
        )


def _cmd_kline(client: StockClient, args) -> None:
    bars = client.get_kline(args.symbol, period=args.period, count=args.count, adjust=args.adjust)
    fmt = "{:<17} {:>9} {:>9} {:>9} {:>9} {:>14}"
    print(fmt.format("时间", "开", "收", "高", "低", "成交量(股)"))
    for b in bars:
        ts = b.datetime.strftime("%Y-%m-%d %H:%M" if args.period.endswith("m") else "%Y-%m-%d")
        print(fmt.format(ts, f"{b.open:.2f}", f"{b.close:.2f}", f"{b.high:.2f}", f"{b.low:.2f}", f"{b.volume:,}"))


def _cmd_search(client: StockClient, args) -> None:
    for r in client.search(args.keyword):
        print(f"{r.symbol:<10} {r.name:<12} {r.security_type}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stocksdk", description="A股实时行情查询")
    parser.add_argument("--timeout", type=float, default=5.0, help="单次请求超时秒数")
    sub = parser.add_subparsers(dest="command", required=True)

    p_quote = sub.add_parser("quote", help="实时行情")
    p_quote.add_argument("symbols", nargs="+", help="证券代码，如 600519 000001.SZ sh000001")

    p_kline = sub.add_parser("kline", help="K线")
    p_kline.add_argument("symbol")
    p_kline.add_argument("--period", default="day", choices=PERIODS)
    p_kline.add_argument("--count", type=int, default=10)
    p_kline.add_argument("--adjust", default="qfq", choices=ADJUSTS)

    p_search = sub.add_parser("search", help="按名称/代码/拼音搜索")
    p_search.add_argument("keyword")

    args = parser.parse_args(argv)
    client = StockClient(timeout=args.timeout)
    try:
        {"quote": _cmd_quote, "kline": _cmd_kline, "search": _cmd_search}[args.command](client, args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

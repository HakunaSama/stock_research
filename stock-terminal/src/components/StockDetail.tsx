import { useEffect, useRef, useState } from "react";
import { Button, Card, Skeleton } from "antd";
import { StarFilled, StarOutlined } from "@ant-design/icons";
import { motion } from "framer-motion";
import { dirColor, fmtAmountCn, fmtNum, fmtVolume, signNum, signPct } from "@/lib/utils";
import { useMarket } from "@/store/market";
import type { StockQuote } from "@/types/market";
import KlinePanel from "./KlinePanel";
import NewsFeed from "./NewsFeed";
import ResearchCard from "./ResearchCard";

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-subtle bg-inset px-2 py-1.5">
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="mt-0.5 font-mono text-xs font-semibold" style={{ color: tone ?? "var(--text-primary)" }}>
        {value}
      </div>
    </div>
  );
}

// 报价头 —— 全部字段来自实时行情源;价格变动时以方向色轻闪提示。
function QuoteHeader({ quote }: { quote: StockQuote }) {
  const { watchlist, addStock, removeStock } = useMarket();
  const inWatchlist = watchlist.some((w) => w.code === quote.code);
  const color = dirColor(quote.change_pct);
  const prevPrice = useRef(quote.price);
  const [flash, setFlash] = useState<"" | "flash-up" | "flash-down">("");

  useEffect(() => {
    if (quote.price !== prevPrice.current) {
      setFlash(quote.price > prevPrice.current ? "flash-up" : "flash-down");
      prevPrice.current = quote.price;
      const t = setTimeout(() => setFlash(""), 900);
      return () => clearTimeout(t);
    }
  }, [quote.price]);

  const amplitude =
    quote.prev_close > 0 ? ((quote.high - quote.low) / quote.prev_close) * 100 : null;

  return (
    <Card size="small" styles={{ body: { padding: 14 } }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="m-0 font-display text-lg font-bold text-ink">{quote.name}</h1>
            <span className="font-mono text-xs text-ink-3">
              {quote.symbol.slice(0, 2).toUpperCase()} {quote.code}
            </span>
            <Button
              size="small"
              type="text"
              icon={inWatchlist ? <StarFilled style={{ color: "var(--accent)" }} /> : <StarOutlined />}
              onClick={() =>
                inWatchlist
                  ? removeStock(quote.code)
                  : addStock({ code: quote.code, name: quote.name })
              }
            >
              <span className="text-2xs">{inWatchlist ? "已自选" : "加自选"}</span>
            </Button>
          </div>
          <div className={`mt-1.5 flex items-baseline gap-2.5 rounded-md px-1 ${flash}`}>
            <span className="font-mono text-[30px] font-bold leading-none" style={{ color }}>
              {quote.price.toFixed(2)}
            </span>
            <span className="font-mono text-sm font-semibold" style={{ color }}>
              {signNum(quote.change)}
            </span>
            <span className="font-mono text-sm font-semibold" style={{ color }}>
              {signPct(quote.change_pct)}
            </span>
          </div>
          <div className="mt-1.5 font-mono text-2xs text-ink-3">
            {quote.time} · 数据源 {quote.source}
          </div>
        </div>

        <div className="grid flex-1 basis-[420px] grid-cols-2 gap-1.5 min-[480px]:grid-cols-3 sm:grid-cols-5">
          <Stat label="今开" value={quote.open.toFixed(2)} tone={dirColor(quote.open - quote.prev_close)} />
          <Stat label="最高" value={quote.high.toFixed(2)} tone={dirColor(quote.high - quote.prev_close)} />
          <Stat label="最低" value={quote.low.toFixed(2)} tone={dirColor(quote.low - quote.prev_close)} />
          <Stat label="昨收" value={quote.prev_close.toFixed(2)} />
          <Stat label="振幅" value={amplitude != null ? `${amplitude.toFixed(2)}%` : "-"} />
          <Stat label="成交量" value={fmtVolume(quote.volume)} />
          <Stat label="成交额" value={fmtAmountCn(quote.amount)} />
          <Stat label="换手率" value={quote.turnover_rate != null ? `${fmtNum(quote.turnover_rate)}%` : "-"} />
          <Stat label="市盈(TTM)" value={fmtNum(quote.pe_ttm)} />
          <Stat label="市净率" value={fmtNum(quote.pb)} />
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-subtle pt-2 font-mono text-2xs text-ink-3">
        <span>总市值 <span className="text-ink-2">{fmtAmountCn(quote.total_market_cap)}</span></span>
        <span>流通市值 <span className="text-ink-2">{fmtAmountCn(quote.float_market_cap)}</span></span>
      </div>
    </Card>
  );
}

// 主详情区 —— 选中标的的实时报价 + AI 研究 + K线 + 资讯,全真实数据。
export default function StockDetail() {
  const selectedCode = useMarket((s) => s.selectedCode);
  const quote = useMarket((s) => s.quotes[s.selectedCode]);
  const watchName = useMarket(
    (s) => s.watchlist.find((w) => w.code === s.selectedCode)?.name ?? s.selectedCode,
  );

  if (!selectedCode) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-ink-3">
        使用顶部搜索或在左侧股票池中选择一只股票
      </div>
    );
  }

  return (
    <motion.div
      key={selectedCode}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col gap-3"
    >
      {quote ? (
        <QuoteHeader quote={quote} />
      ) : (
        <Card size="small">
          <Skeleton active paragraph={{ rows: 3 }} />
        </Card>
      )}

      <ResearchCard code={selectedCode} name={quote?.name ?? watchName} />
      <KlinePanel code={selectedCode} />
      <NewsFeed code={selectedCode} />
    </motion.div>
  );
}

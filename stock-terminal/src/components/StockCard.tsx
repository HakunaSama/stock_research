import { useState } from "react";
import { motion } from "framer-motion";
import { Target, ArrowUpRight, ArrowDownRight, Layers, FlaskConical } from "lucide-react";
import type { StockAnalysis, ViewTab } from "@/types/analysis";
import { dirColor, signPct, signNum, fmtMoney } from "@/lib/utils";
import { useTerminal } from "@/store/terminal";
import { researchRuns } from "@/data/research";
import ScoreGrid from "./ScoreGrid";
import ProgressBars from "./ProgressBars";
import AttributeRows from "./AttributeRows";
import NewsFeed from "./NewsFeed";
import AnimatedNumber from "./AnimatedNumber";

interface Props {
  data: StockAnalysis;
  index: number;
}

const TABS: ViewTab[] = ["推荐持有", "最新观点", "位置"];

function ActionBadge({ action }: { action: string }) {
  const buy = action.includes("买");
  const c = buy ? "var(--up)" : "var(--accent)";
  const bg = buy ? "var(--up-dim)" : "var(--accent-dim)";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-sm px-2 py-1 font-display text-xs font-700"
      style={{ color: c, background: bg, boxShadow: `inset 0 0 0 1px ${c}` }}
    >
      <Target size={12} strokeWidth={2.6} />
      {action}
    </span>
  );
}

function LevelCell({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-sm border border-subtle bg-inset px-2 py-1.5">
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="mt-0.5 font-mono text-xs font-600" style={{ color: tone ?? "var(--text-primary)" }}>
        {value}
      </div>
    </div>
  );
}

export default function StockCard({ data, index }: Props) {
  const [tab, setTab] = useState<ViewTab>("推荐持有");
  const { selectedId, openResearch } = useTerminal();
  const active = selectedId === data.id;
  const hasResearch = data.id in researchRuns;
  const { quote, position, verdict, levels } = data;
  const upColor = dirColor(quote.changePct);

  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: index * 0.12, ease: [0.16, 1, 0.3, 1] }}
      className="relative flex flex-col gap-2.5 rounded-lg border bg-panel p-3 transition-colors"
      style={{
        borderColor: active ? "var(--accent)" : "var(--border-subtle)",
        boxShadow: active ? "0 0 0 1px var(--accent), 0 8px 30px rgba(0,0,0,0.35)" : "0 8px 30px rgba(0,0,0,0.25)",
      }}
    >
      {/* 卡头 */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-ink-3">{quote.code}</span>
            <span className="font-display text-[15px] font-700 text-ink">{quote.name}</span>
            <span className="font-mono text-2xs text-ink-3">{quote.time}</span>
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-[22px] font-700 leading-none" style={{ color: upColor }}>
              {quote.price.toFixed(2)}
            </span>
            <span className="font-mono text-xs font-600" style={{ color: upColor }}>
              {signNum(quote.changeAbs)}
            </span>
            <AnimatedNumber
              value={quote.changePct}
              digits={2}
              prefix={quote.changePct > 0 ? "+" : ""}
              suffix="%"
              className="font-mono text-[22px] font-700 leading-none"
            />
          </div>
        </div>
        <ActionBadge action={verdict.action} />
      </div>

      {/* 持仓 / 可买 */}
      <div className="flex items-center justify-between rounded-sm border border-subtle bg-inset px-2.5 py-1.5">
        {position.has ? (
          <>
            <span className="text-2xs text-ink-3">
              持仓 {position.shares} 股 · 成本 {position.cost?.toFixed(2)}
            </span>
            <span className="font-mono text-xs font-600" style={{ color: dirColor(position.pnl ?? 0) }}>
              {position.pnl! > 0 ? "+" : ""}
              {fmtMoney(position.pnl ?? 0)}（{signPct(position.pnlPct ?? 0)}）
            </span>
          </>
        ) : (
          <>
            <span className="text-2xs text-ink-3">未持仓 · 可买</span>
            <span className="font-mono text-xs font-600 text-ink">
              {fmtMoney(position.buyableAmount ?? 0)} 元 / 约 {position.buyableShares} 股
            </span>
          </>
        )}
      </div>

      {/* 核心依据面板 */}
      <div className="relative overflow-hidden rounded-md border p-2.5" style={{ borderColor: "var(--accent)", background: "var(--accent-dim)" }}>
        <div className="flex items-center justify-between">
          <span className="font-display text-2xs font-600 uppercase tracking-wider" style={{ color: "var(--accent)" }}>
            核心依据
          </span>
          <div className="flex items-center gap-2">
            {hasResearch && (
              <button
                onClick={() => openResearch(data.id)}
                className="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-2xs font-600 transition-colors"
                style={{ color: "var(--accent)", background: "rgba(25,209,159,0.14)" }}
              >
                <FlaskConical size={10} />
                研究过程
              </button>
            )}
            <span className="font-mono text-2xs" style={{ color: "var(--accent)" }}>
              置信度 {verdict.confidence}%
            </span>
          </div>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-ink">{verdict.headline}</p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {verdict.tags.map((t) => (
            <span key={t} className="rounded-sm px-1.5 py-0.5 text-2xs" style={{ background: "rgba(25,209,159,0.14)", color: "var(--accent)" }}>
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* 观点切换 Tab */}
      <div className="flex items-center gap-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex-1 rounded-sm px-2 py-1 text-2xs font-500 transition-colors"
            style={{
              background: tab === t ? "var(--bg-elevated)" : "transparent",
              color: tab === t ? "var(--text-primary)" : "var(--text-muted)",
              boxShadow: tab === t ? "inset 0 0 0 1px var(--border-strong)" : "none",
            }}
          >
            {t === "位置" ? `位置 ${data.positionPct}%` : t}
          </button>
        ))}
      </div>

      {/* 价位矩阵 */}
      <div className="grid grid-cols-3 gap-1.5">
        <LevelCell label="低阻区" value={levels.supportLow.toFixed(2)} tone="var(--down)" />
        <LevelCell label="压力位" value={levels.resistance.toFixed(2)} tone="var(--up)" />
        <LevelCell label="二支撑" value={levels.secondSupport.toFixed(2)} />
        <LevelCell label="均线" value={levels.maLine.toFixed(2)} tone="var(--blue)" />
        <LevelCell label="成交量" value={levels.turnover} />
        <LevelCell label="计划买入" value={levels.plannedBuy} tone="var(--accent)" />
      </div>

      {/* 六维评分 */}
      <ScoreGrid scores={data.scores} />

      {/* 双进度条 */}
      <ProgressBars micro={data.microProgress} composite={data.compositeProgress} />

      {/* 操作建议 */}
      <div className="grid grid-cols-3 gap-1.5">
        <div className="col-span-3 flex items-center gap-1.5 rounded-sm border border-subtle bg-inset px-2 py-1.5">
          <Layers size={12} className="text-ink-3" />
          <span className="text-2xs text-ink-2">{verdict.ops}</span>
        </div>
        <div className="col-span-3 grid grid-cols-2 gap-1.5">
          <div className="flex items-center gap-1.5 rounded-sm border-l-2 bg-inset px-2 py-1.5" style={{ borderColor: "var(--up)" }}>
            <ArrowDownRight size={12} style={{ color: "var(--up)" }} />
            <div>
              <div className="text-2xs text-ink-3">买点</div>
              <div className="font-mono text-2xs font-600" style={{ color: "var(--up)" }}>{verdict.buyPoint}</div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 rounded-sm border-l-2 bg-inset px-2 py-1.5" style={{ borderColor: "var(--down)" }}>
            <ArrowUpRight size={12} style={{ color: "var(--down)" }} />
            <div>
              <div className="text-2xs text-ink-3">卖点</div>
              <div className="font-mono text-2xs font-600" style={{ color: "var(--down)" }}>{verdict.sellPoint}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 属性解读 */}
      <AttributeRows rows={data.attributes} />

      {/* 资讯流 */}
      <NewsFeed items={data.news} />
    </motion.article>
  );
}

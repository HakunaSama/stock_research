import { motion } from "framer-motion";
import { ListChecks, Sparkles } from "lucide-react";
import { watchlist } from "@/data/watchlist";
import { dirColor, signPct } from "@/lib/utils";
import { useTerminal, researchedIds } from "@/store/terminal";

function scoreColor(v: number): string {
  if (v >= 90) return "var(--accent)";
  if (v >= 75) return "var(--blue)";
  if (v >= 60) return "var(--amber)";
  return "var(--text-secondary)";
}

export default function Watchlist() {
  const { selectedId, select, openResearch } = useTerminal();

  // 点击候选股：已深度研究的 → 打开研究抽屉；未研究的 → 仅选中（主区显示精简候选卡）。
  function onPick(code: string) {
    if (researchedIds.has(code)) {
      openResearch(code);
    } else {
      select(code);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-subtle bg-panel">
      <div className="flex items-center justify-between border-b border-subtle px-3 py-2">
        <div className="flex items-center gap-1.5">
          <ListChecks size={13} style={{ color: "var(--accent)" }} />
          <span className="font-display text-xs font-600 text-ink">候选池 · 按评分排序</span>
        </div>
        <span className="font-mono text-2xs text-ink-3">{watchlist.length} 只</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {watchlist.map((w, i) => {
          const active = selectedId === w.code;
          const researched = researchedIds.has(w.code);
          return (
            <motion.button
              key={w.code}
              onClick={() => onPick(w.code)}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, delay: i * 0.03 }}
              className="relative flex w-full items-start gap-2 border-b border-subtle/60 py-2 pl-3 pr-3 text-left transition-colors hover:bg-elevated"
              style={{ background: active ? "var(--bg-elevated)" : "transparent" }}
              title={researched ? "查看深度研究" : "选中查看（尚未深度研究）"}
            >
              {/* 选中态左侧竖色条（行情软件常见的单选高亮） */}
              <span
                className="absolute left-0 top-0 h-full w-0.5 rounded-r"
                style={{ background: active ? "var(--accent)" : "transparent" }}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1">
                  <div className="flex min-w-0 items-center gap-1.5 truncate">
                    <span className="font-mono text-2xs text-ink-3">{w.code}</span>
                    <span className="truncate font-display text-xs font-600 text-ink">{w.name}</span>
                    {researched && (
                      <Sparkles size={10} style={{ color: "var(--accent)" }} aria-label="已深度研究" />
                    )}
                  </div>
                  <span
                    className="shrink-0 rounded-sm px-1 font-mono text-2xs font-700"
                    style={{ color: scoreColor(w.score), background: "var(--bg-inset)" }}
                  >
                    {w.score}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className="font-mono text-2xs text-ink-2">{w.price.toFixed(2)}</span>
                  <span className="font-mono text-2xs font-600" style={{ color: dirColor(w.changePct) }}>
                    {signPct(w.changePct)}
                  </span>
                  <span className="font-mono text-2xs text-ink-3">{w.marketCap}</span>
                </div>
                <div className="mt-0.5 truncate text-2xs text-ink-3">{w.note}</div>
              </div>
            </motion.button>
          );
        })}
      </div>

      <div className="border-t border-subtle px-3 py-1.5 text-center text-2xs text-ink-3">
        <Sparkles size={9} className="mr-1 inline" style={{ color: "var(--accent)" }} />
        标记项已完成深度研究 · 点击查看
      </div>
    </div>
  );
}

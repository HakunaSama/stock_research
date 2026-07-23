import { motion } from "framer-motion";
import { RotateCw, Check, X } from "lucide-react";
import type { AttemptHistory } from "@/types/analysis";

interface Props {
  history: AttemptHistory[];
  threshold: number;
}

// 评分重跑时间线 —— 每次 attempt 是一次完整 ODR 重跑；分低（✗）就再跑，
// 直到达标（✓）。这正是"最终评分过低就重新走 ODR 流程"的可视化。
export default function RetryTimeline({ history, threshold }: Props) {
  return (
    <div className="rounded-md border border-subtle bg-inset p-2.5">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <RotateCw size={12} className="text-accent" />
          <span className="font-display text-2xs font-600 uppercase tracking-wider text-ink-3">
            评分 · 重跑闭环
          </span>
        </div>
        <span className="font-mono text-2xs text-ink-3">阈值 {threshold.toFixed(1)}</span>
      </div>

      <div className="flex flex-col gap-1.5">
        {history.map((h, i) => {
          const color = h.accepted ? "var(--accent)" : "var(--down)";
          return (
            <motion.div
              key={h.attempt}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="flex items-center gap-2"
            >
              <span className="w-10 shrink-0 font-mono text-2xs text-ink-3">
                第{h.attempt}轮
              </span>
              {/* 分数胶囊 */}
              <span
                className="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-xs font-700"
                style={{ color, background: h.accepted ? "var(--accent-dim)" : "var(--down-dim)", boxShadow: `inset 0 0 0 1px ${color}` }}
              >
                {h.accepted ? <Check size={11} strokeWidth={3} /> : <X size={11} strokeWidth={3} />}
                {h.score.toFixed(1)}
              </span>
              {/* 该轮 ODR 概览 */}
              <span className="flex-1 truncate text-2xs text-ink-2" title={h.judge.reasons}>
                {h.supervisor_rounds} 轮编排 · {h.sub_topics.length} 子研究 · {h.judge.worst_gap}
              </span>
              {!h.accepted && i < history.length - 1 && (
                <span className="shrink-0 font-mono text-2xs" style={{ color: "var(--down)" }}>
                  ↻ 重跑
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

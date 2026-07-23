import { motion } from "framer-motion";
import type { Scores } from "@/types/analysis";

interface Props {
  scores: Scores;
}

const items: { key: keyof Scores; label: string }[] = [
  { key: "composite", label: "综合" },
  { key: "price", label: "价格" },
  { key: "volume", label: "量能" },
  { key: "logic", label: "逻辑" },
  { key: "sentiment", label: "情绪" },
  { key: "market", label: "大盘" },
];

function scoreColor(v: number): string {
  if (v >= 80) return "var(--accent)";
  if (v >= 60) return "var(--blue)";
  if (v >= 45) return "var(--amber)";
  return "var(--down)";
}

export default function ScoreGrid({ scores }: Props) {
  return (
    <div className="grid grid-cols-6 gap-1.5">
      {items.map((it, i) => {
        const v = scores[it.key];
        const c = scoreColor(v);
        return (
          <div
            key={it.key}
            className="flex flex-col items-center rounded-sm border border-subtle bg-inset px-1 pt-1.5 pb-1"
          >
            <span
              className="font-mono text-[15px] font-700 leading-none"
              style={{ color: c }}
            >
              {v}
            </span>
            <span className="mt-1 text-2xs text-ink-3">{it.label}</span>
            <div className="mt-1 h-[3px] w-full overflow-hidden rounded-full bg-strong/60">
              <motion.div
                className="h-full rounded-full"
                style={{ background: c }}
                initial={{ width: 0 }}
                whileInView={{ width: `${v}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.9, delay: 0.1 + i * 0.06, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

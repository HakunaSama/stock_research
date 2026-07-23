import { motion } from "framer-motion";
import { Microscope, Lightbulb, Link2, Wrench } from "lucide-react";
import type { SubFinding } from "@/types/analysis";

interface Props {
  finding: SubFinding;
  index: number;
}

// 单个子研究员对一个子主题的调研发现：主题 → 笔记 → think_tool 反思 → 来源。
// 对应 ODR 里一个并行子研究单元（sub-agent）的产出。
export default function SubFindingCard({ finding, index }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-md border border-subtle bg-panel-2 p-2.5"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <Microscope size={12} className="shrink-0 text-accent" />
          <span className="truncate font-display text-xs font-600 text-ink">{finding.topic}</span>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 font-mono text-2xs text-ink-3">
          <Wrench size={10} />
          {finding.tool_calls} 次检索
        </span>
      </div>

      <p className="mt-1.5 text-2xs leading-relaxed text-ink-2">{finding.notes}</p>

      {finding.reflections.length > 0 && (
        <div className="mt-2 rounded-sm border-l-2 bg-inset px-2 py-1.5" style={{ borderColor: "var(--amber)" }}>
          <div className="mb-1 flex items-center gap-1">
            <Lightbulb size={10} style={{ color: "var(--amber)" }} />
            <span className="font-display text-2xs font-600 uppercase tracking-wider text-ink-3">
              反思 · think_tool
            </span>
          </div>
          <ul className="flex flex-col gap-0.5">
            {finding.reflections.map((r, i) => (
              <li key={i} className="flex gap-1 text-2xs leading-snug text-ink-2">
                <span style={{ color: "var(--amber)" }}>›</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {finding.sources.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {finding.sources.map((s, i) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 truncate text-2xs text-ink-3 transition-colors hover:text-accent"
              title={s.title}
            >
              <Link2 size={10} className="shrink-0" />
              <span className="truncate">{s.title}</span>
              <span className="shrink-0 font-mono text-ink-3/70">{s.date}</span>
            </a>
          ))}
        </div>
      )}
    </motion.div>
  );
}

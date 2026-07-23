import { Clock } from "lucide-react";
import type { NewsItem } from "@/types/analysis";

interface Props {
  items: NewsItem[];
}

export default function NewsFeed({ items }: Props) {
  return (
    <div className="flex flex-col">
      <div className="mb-1.5 flex items-center gap-1.5">
        <Clock size={11} className="text-ink-3" />
        <span className="font-display text-2xs font-600 uppercase tracking-wider text-ink-3">
          资讯流
        </span>
      </div>
      <div className="relative flex flex-col gap-1.5 pl-3">
        <div className="absolute left-[3px] top-1 bottom-1 w-px bg-subtle" />
        {items.map((n, i) => (
          <div key={i} className="relative">
            <div
              className="absolute -left-[10px] top-1 h-1.5 w-1.5 rounded-full"
              style={{ background: i === 0 ? "var(--accent)" : "var(--border-strong)" }}
            />
            <div className="flex items-baseline gap-2">
              <span className="shrink-0 font-mono text-2xs text-ink-3">{n.time}</span>
              <span className="text-2xs leading-snug text-ink-2">{n.text}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

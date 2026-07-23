import type { AttrRow } from "@/types/analysis";

interface Props {
  rows: AttrRow[];
}

const toneMap: Record<AttrRow["tone"], { border: string; text: string }> = {
  up: { border: "var(--up)", text: "var(--up)" },
  down: { border: "var(--down)", text: "var(--down)" },
  info: { border: "var(--blue)", text: "var(--blue)" },
  neutral: { border: "var(--border-strong)", text: "var(--text-secondary)" },
};

export default function AttributeRows({ rows }: Props) {
  return (
    <div className="flex flex-col gap-1">
      {rows.map((r) => {
        const t = toneMap[r.tone];
        return (
          <div
            key={r.key}
            className="flex items-start gap-2 rounded-sm border-l-2 bg-inset/60 py-1 pl-2 pr-1.5"
            style={{ borderColor: t.border }}
          >
            <span
              className="mt-px shrink-0 font-display text-2xs font-600"
              style={{ color: t.text }}
            >
              {r.key}
            </span>
            <span className="text-2xs leading-snug text-ink-2">{r.text}</span>
          </div>
        );
      })}
    </div>
  );
}

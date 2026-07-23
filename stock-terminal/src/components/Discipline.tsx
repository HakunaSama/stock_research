import { ShieldCheck } from "lucide-react";
import { discipline } from "@/data/discipline";

export default function Discipline() {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--amber)", background: "rgba(245,181,68,0.06)" }}>
      <div className="mb-2 flex items-center gap-1.5">
        <ShieldCheck size={13} style={{ color: "var(--amber)" }} />
        <span className="font-display text-xs font-700" style={{ color: "var(--amber)" }}>
          执行纪律
        </span>
      </div>
      <ol className="flex flex-col gap-1.5">
        {discipline.map((d) => (
          <li key={d.order} className="flex items-start gap-2">
            <span
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded-sm font-mono text-2xs font-700"
              style={{ background: "rgba(245,181,68,0.16)", color: "var(--amber)" }}
            >
              {d.order}
            </span>
            <span className="text-2xs leading-snug text-ink-2">{d.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

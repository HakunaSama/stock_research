import { motion } from "framer-motion";

interface Bar {
  label: string;
  value: number;
  color: string;
}

interface Props {
  micro: number;
  composite: number;
}

function Row({ label, value, color }: Bar) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-2xs text-ink-3">{label}</span>
        <span className="font-mono text-2xs font-600" style={{ color }}>
          {value}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-inset">
        <motion.div
          className="relative h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          whileInView={{ width: `${value}%` }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  );
}

export default function ProgressBars({ micro, composite }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Row label="微观运图" value={micro} color="var(--blue)" />
      <Row label="综合度" value={composite} color="var(--up)" />
    </div>
  );
}

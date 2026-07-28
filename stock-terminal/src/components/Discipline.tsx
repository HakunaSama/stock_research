import { Card } from "antd";
import { SafetyCertificateOutlined } from "@ant-design/icons";
import { discipline } from "@/data/discipline";

// 执行纪律 —— 固定的产品文案(交易纪律清单),非行情数据。
export default function Discipline() {
  return (
    <Card
      size="small"
      title={
        <span className="flex items-center gap-1.5 font-display text-xs font-semibold" style={{ color: "var(--amber)" }}>
          <SafetyCertificateOutlined />
          执行纪律
        </span>
      }
      style={{ borderColor: "rgba(217,119,6,0.3)" }}
      styles={{ body: { padding: "8px 12px" } }}
    >
      <ol className="m-0 flex list-none flex-col gap-1.5 p-0">
        {discipline.map((d) => (
          <li key={d.order} className="flex items-start gap-2">
            <span
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded-sm font-mono text-2xs font-bold"
              style={{ background: "rgba(217,119,6,0.12)", color: "var(--amber)" }}
            >
              {d.order}
            </span>
            <span className="text-2xs leading-snug text-ink-2">{d.text}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

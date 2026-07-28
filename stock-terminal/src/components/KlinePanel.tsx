import { useEffect, useState } from "react";
import { Card, Empty, Segmented, Skeleton } from "antd";
import { AreaChartOutlined } from "@ant-design/icons";
import { fetchLiveKline } from "@/lib/market";
import type { KlineData } from "@/types/analysis";
import type { KlinePeriod } from "@/types/market";
import KlineChart from "./KlineChart";
import KlineFeaturePanel from "./KlineFeaturePanel";

const PERIODS: { key: KlinePeriod; label: string; count: number }[] = [
  { key: "60m", label: "60分", count: 160 },
  { key: "day", label: "日K", count: 180 },
  { key: "week", label: "周K", count: 160 },
  { key: "month", label: "月K", count: 120 },
];

// K线面板 —— 任意标的的实时 OHLCV(前复权),支持周期切换;
// 底部展示由后端实时计算的六维技术特征。
export default function KlinePanel({ code }: { code: string }) {
  const [period, setPeriod] = useState<KlinePeriod>("day");
  const [data, setData] = useState<KlineData | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    let alive = true;
    setState("loading");
    const cfg = PERIODS.find((p) => p.key === period)!;
    fetchLiveKline(code, period, cfg.count).then((live) => {
      if (!alive) return;
      setData(live);
      setState(live ? "ok" : "error");
    });
    return () => {
      alive = false;
    };
  }, [code, period]);

  return (
    <Card
      size="small"
      title={
        <span className="flex items-center gap-1.5 font-display text-xs font-semibold">
          <AreaChartOutlined style={{ color: "var(--accent)" }} />
          K线 · 前复权
        </span>
      }
      extra={
        <Segmented
          size="small"
          value={period}
          onChange={(v) => setPeriod(v as KlinePeriod)}
          options={PERIODS.map((p) => ({ label: p.label, value: p.key }))}
        />
      }
      styles={{ body: { padding: 12 } }}
    >
      {state === "loading" ? (
        <Skeleton.Node active style={{ width: "100%", height: 280 }} />
      ) : state === "error" || !data ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span className="text-2xs text-ink-3">行情源暂不可用,稍后自动重试</span>}
        />
      ) : (
        <>
          <KlineChart data={data} />
          {data.features && (
            <div className="mt-2.5 border-t border-subtle pt-2.5">
              <KlineFeaturePanel features={data.features} />
            </div>
          )}
        </>
      )}
    </Card>
  );
}

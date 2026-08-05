import { useEffect, useRef, useState } from "react";
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

const DEFAULT_CHART_HEIGHT = 360;
const MIN_CHART_HEIGHT = 240;
const MAX_CHART_HEIGHT = 640;
const CHART_HEIGHT_KEY = "cheese:kline-height";

function clampChartHeight(value: number) {
  return Math.min(MAX_CHART_HEIGHT, Math.max(MIN_CHART_HEIGHT, Math.round(value)));
}

function initialChartHeight() {
  if (typeof window === "undefined") return DEFAULT_CHART_HEIGHT;
  const saved = Number(window.localStorage.getItem(CHART_HEIGHT_KEY));
  return Number.isFinite(saved) && saved > 0 ? clampChartHeight(saved) : DEFAULT_CHART_HEIGHT;
}

// K线面板 —— 任意标的的实时 OHLCV(前复权),支持周期切换;
// 底部展示由后端实时计算的六维技术特征。
export default function KlinePanel({ code }: { code: string }) {
  const [period, setPeriod] = useState<KlinePeriod>("day");
  const [data, setData] = useState<KlineData | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [chartHeight, setChartHeight] = useState(initialChartHeight);
  const [resizing, setResizing] = useState(false);
  const dragStart = useRef<{ y: number; height: number } | null>(null);

  useEffect(() => {
    function updateFromPointer(clientY: number) {
      if (!dragStart.current) return;
      setChartHeight(clampChartHeight(dragStart.current.height + clientY - dragStart.current.y));
    }

    function finishResize(clientY: number) {
      if (!dragStart.current) return;
      const next = clampChartHeight(dragStart.current.height + clientY - dragStart.current.y);
      dragStart.current = null;
      setChartHeight(next);
      setResizing(false);
      window.localStorage.setItem(CHART_HEIGHT_KEY, String(next));
    }

    const onPointerMove = (event: PointerEvent) => updateFromPointer(event.clientY);
    const onPointerUp = (event: PointerEvent) => finishResize(event.clientY);
    const onPointerCancel = () => {
      dragStart.current = null;
      setResizing(false);
    };
    // Mouse listeners are a compatibility fallback for embedded browsers that
    // dispatch mouse drags without the complete Pointer Events sequence.
    const onMouseMove = (event: MouseEvent) => updateFromPointer(event.clientY);
    const onMouseUp = (event: MouseEvent) => finishResize(event.clientY);

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerCancel);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerCancel);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  function saveChartHeight(height: number) {
    window.localStorage.setItem(CHART_HEIGHT_KEY, String(height));
  }

  function resizeBy(delta: number) {
    setChartHeight((current) => {
      const next = clampChartHeight(current + delta);
      saveChartHeight(next);
      return next;
    });
  }

  function resetChartHeight() {
    setChartHeight(DEFAULT_CHART_HEIGHT);
    saveChartHeight(DEFAULT_CHART_HEIGHT);
  }

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
        <Skeleton.Node active style={{ width: "100%", height: chartHeight }} />
      ) : state === "error" || !data ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span className="text-2xs text-ink-3">行情源暂不可用,稍后自动重试</span>}
        />
      ) : (
        <>
          <KlineChart data={data} height={chartHeight} />
          <div
            data-testid="kline-resize-handle"
            role="separator"
            tabIndex={0}
            aria-label="调整 K 线图高度"
            aria-orientation="horizontal"
            aria-valuemin={MIN_CHART_HEIGHT}
            aria-valuemax={MAX_CHART_HEIGHT}
            aria-valuenow={chartHeight}
            title="上下拖动调整高度 · 双击恢复默认"
            className={`group mt-1 flex h-4 cursor-ns-resize touch-none items-center justify-center rounded-sm outline-none transition-colors hover:bg-accent-dim focus-visible:bg-accent-dim ${resizing ? "bg-accent-dim" : ""}`}
            onPointerDown={(event) => {
              if (!dragStart.current) dragStart.current = { y: event.clientY, height: chartHeight };
              setResizing(true);
            }}
            onMouseDown={(event) => {
              if (!dragStart.current) dragStart.current = { y: event.clientY, height: chartHeight };
              setResizing(true);
            }}
            onDoubleClick={resetChartHeight}
            onKeyDown={(event) => {
              if (event.key === "ArrowUp") {
                event.preventDefault();
                resizeBy(event.shiftKey ? -40 : -16);
              } else if (event.key === "ArrowDown") {
                event.preventDefault();
                resizeBy(event.shiftKey ? 40 : 16);
              } else if (event.key === "Home") {
                event.preventDefault();
                setChartHeight(MIN_CHART_HEIGHT);
                saveChartHeight(MIN_CHART_HEIGHT);
              } else if (event.key === "End") {
                event.preventDefault();
                setChartHeight(MAX_CHART_HEIGHT);
                saveChartHeight(MAX_CHART_HEIGHT);
              }
            }}
          >
            <span className="h-1 w-12 rounded-full bg-strong transition-colors group-hover:bg-accent" />
            <span className="sr-only">当前高度 {chartHeight} 像素</span>
          </div>
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

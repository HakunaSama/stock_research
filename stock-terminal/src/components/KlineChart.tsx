import { useMemo, useRef, useState } from "react";
import type { KlineData } from "@/types/analysis";

// 手绘 SVG 蜡烛图 —— 零第三方图表依赖。A 股惯例:涨红跌绿。
// 叠加 MA5/MA20/MA60 均线与成交量柱,右侧价格轴,支撑/压力标线。
// 交互:鼠标悬停显示十字线 + 单根 K 线明细浮层(开/高/低/收/涨跌/量)。
//
// 注意:SVG presentation attribute 里 CSS 变量不生效,故用与 theme.css
// 对齐的固定 hex 常量。

const UP = "#e5484d"; // --up
const DOWN = "#00a05a"; // --down
const GRID = "#eae8f4"; // --border-subtle
const AXIS = "#8b89a6"; // --text-muted
const CROSS = "#45446b"; // --text-secondary
const MA5 = "#8247ff";
const MA20 = "#3e63dd";
const MA60 = "#d97706";

interface Props {
  data: KlineData;
  maxBars?: number;
}

function movingAvg(closes: number[], window: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i + 1 < window) return null;
    let s = 0;
    for (let k = i + 1 - window; k <= i; k++) s += closes[k];
    return s / window;
  });
}

export default function KlineChart({ data, maxBars = 120 }: Props) {
  const bars = useMemo(() => data.bars.slice(-maxBars), [data.bars, maxBars]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const geom = useMemo(() => {
    if (bars.length === 0) return null;
    const W = 640;
    const H = 280;
    const volH = 52;
    const padL = 6;
    const padR = 48; // 右侧价格轴
    const padT = 10;
    const gap = 10;
    const priceH = H - volH - gap - padT;

    const hi = Math.max(...bars.map((b) => b.h));
    const lo = Math.min(...bars.map((b) => b.l));
    const span = hi - lo || 1;
    const plotW = W - padL - padR;
    const step = plotW / bars.length;
    const bodyW = Math.max(1.5, step * 0.62);

    const yPrice = (p: number) => padT + (1 - (p - lo) / span) * priceH;

    const closes = bars.map((b) => b.c);
    const ma5 = movingAvg(closes, 5);
    const ma20 = movingAvg(closes, 20);
    const ma60 = movingAvg(closes, 60);
    const maxVol = Math.max(...bars.map((b) => b.v)) || 1;
    const volTop = padT + priceH + gap;
    const yVol = (v: number) => volTop + (1 - v / maxVol) * volH;
    const cx = (i: number) => padL + step * i + step / 2;

    const maPath = (ma: (number | null)[]) => {
      let d = "";
      ma.forEach((v, i) => {
        if (v == null) return;
        d += `${d ? "L" : "M"}${cx(i).toFixed(1)},${yPrice(v).toFixed(1)}`;
      });
      return d;
    };

    return {
      W, H, padL, padR, padT, priceH, volTop, volH,
      hi, lo, step, bodyW, yPrice, yVol, cx,
      ma5Path: maPath(ma5), ma20Path: maPath(ma20), ma60Path: maPath(ma60),
      lastClose: closes[closes.length - 1],
    };
  }, [bars]);

  if (!geom || bars.length === 0) {
    return <div className="py-6 text-center text-2xs text-ink-3">暂无 K 线数据</div>;
  }

  const f = data.features;
  const support = f?.key_levels.support ?? null;
  const resistance = f?.key_levels.resistance ?? null;

  function onMove(e: React.MouseEvent) {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect || !geom) return;
    const x = ((e.clientX - rect.left) / rect.width) * geom.W;
    const idx = Math.floor((x - geom.padL) / geom.step);
    setHover(idx >= 0 && idx < bars.length ? idx : null);
  }

  const hb = hover != null ? bars[hover] : null;
  const hbPrev = hover != null && hover > 0 ? bars[hover - 1] : null;
  const hbPct = hb && hbPrev ? ((hb.c - hbPrev.c) / hbPrev.c) * 100 : null;
  // 浮层放在光标另一侧,避免遮挡
  const tipLeft = hover != null && geom ? (geom.cx(hover) / geom.W) * 100 : 0;

  return (
    <div className="w-full">
      <div
        ref={wrapRef}
        className="relative"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <svg viewBox={`0 0 ${geom.W} ${geom.H}`} className="w-full" style={{ display: "block" }}>
          {/* 价格网格 */}
          {[0, 0.25, 0.5, 0.75, 1].map((r) => {
            const y = geom.padT + r * geom.priceH;
            const price = geom.hi - r * (geom.hi - geom.lo);
            return (
              <g key={r}>
                <line x1={geom.padL} y1={y} x2={geom.W - geom.padR} y2={y} stroke={GRID} strokeWidth={0.5} strokeDasharray="2 3" />
                <text x={geom.W - geom.padR + 4} y={y + 3} fontSize={8.5} fill={AXIS} fontFamily="ui-monospace, monospace">
                  {price.toFixed(2)}
                </text>
              </g>
            );
          })}

          {/* 支撑 / 压力 */}
          {support != null && (
            <g>
              <line x1={geom.padL} y1={geom.yPrice(support)} x2={geom.W - geom.padR} y2={geom.yPrice(support)} stroke={DOWN} strokeWidth={0.7} strokeDasharray="4 2" opacity={0.55} />
              <text x={geom.padL + 2} y={geom.yPrice(support) - 2} fontSize={8} fill={DOWN} fontFamily="ui-monospace, monospace">支撑 {support.toFixed(2)}</text>
            </g>
          )}
          {resistance != null && (
            <g>
              <line x1={geom.padL} y1={geom.yPrice(resistance)} x2={geom.W - geom.padR} y2={geom.yPrice(resistance)} stroke={UP} strokeWidth={0.7} strokeDasharray="4 2" opacity={0.55} />
              <text x={geom.padL + 2} y={geom.yPrice(resistance) - 2} fontSize={8} fill={UP} fontFamily="ui-monospace, monospace">压力 {resistance.toFixed(2)}</text>
            </g>
          )}

          {/* 蜡烛 + 量柱 */}
          {bars.map((b, i) => {
            const up = b.c >= b.o;
            const color = up ? UP : DOWN;
            const x = geom.cx(i);
            const yO = geom.yPrice(b.o);
            const yC = geom.yPrice(b.c);
            const dim = hover != null && hover !== i ? 0.55 : 1;
            return (
              <g key={i} opacity={dim}>
                <line x1={x} y1={geom.yPrice(b.h)} x2={x} y2={geom.yPrice(b.l)} stroke={color} strokeWidth={0.8} />
                <rect x={x - geom.bodyW / 2} y={Math.min(yO, yC)} width={geom.bodyW} height={Math.max(0.8, Math.abs(yC - yO))} fill={color} />
                <rect x={x - geom.bodyW / 2} y={geom.yVol(b.v)} width={geom.bodyW} height={geom.volTop + geom.volH - geom.yVol(b.v)} fill={color} opacity={0.4} />
              </g>
            );
          })}

          {/* 均线 */}
          <path d={geom.ma5Path} fill="none" stroke={MA5} strokeWidth={1} opacity={0.9} />
          <path d={geom.ma20Path} fill="none" stroke={MA20} strokeWidth={1} opacity={0.9} />
          <path d={geom.ma60Path} fill="none" stroke={MA60} strokeWidth={1} opacity={0.9} />

          {/* 最新价横标 */}
          <line x1={geom.padL} y1={geom.yPrice(geom.lastClose)} x2={geom.W - geom.padR} y2={geom.yPrice(geom.lastClose)} stroke={AXIS} strokeWidth={0.5} opacity={0.4} />

          {/* 十字线 */}
          {hb && hover != null && (
            <g pointerEvents="none">
              <line x1={geom.cx(hover)} y1={geom.padT} x2={geom.cx(hover)} y2={geom.volTop + geom.volH} stroke={CROSS} strokeWidth={0.5} strokeDasharray="3 3" opacity={0.7} />
              <line x1={geom.padL} y1={geom.yPrice(hb.c)} x2={geom.W - geom.padR} y2={geom.yPrice(hb.c)} stroke={CROSS} strokeWidth={0.5} strokeDasharray="3 3" opacity={0.7} />
              <rect x={geom.W - geom.padR + 1} y={geom.yPrice(hb.c) - 6} width={44} height={12} rx={2} fill="#11023b" stroke={CROSS} strokeWidth={0.4} />
              <text x={geom.W - geom.padR + 23} y={geom.yPrice(hb.c) + 3} fontSize={8} fill="#ffffff" textAnchor="middle" fontFamily="ui-monospace, monospace">
                {hb.c.toFixed(2)}
              </text>
            </g>
          )}
        </svg>

        {/* 悬停明细浮层 */}
        {hb && (
          <div
            className="pointer-events-none absolute top-1 z-10 rounded-md border border-strong bg-panel/95 px-2.5 py-1.5 font-mono text-2xs backdrop-blur-sm"
            style={{
              [tipLeft > 55 ? "right" : "left"]: `${tipLeft > 55 ? 100 - tipLeft + 3 : tipLeft + 3}%`,
              boxShadow: "var(--shadow-pop)",
            } as React.CSSProperties}
          >
            <div className="mb-0.5 text-ink-3">{hb.t}</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
              <span className="text-ink-3">开 <span className="text-ink">{hb.o.toFixed(2)}</span></span>
              <span className="text-ink-3">高 <span className="text-ink">{hb.h.toFixed(2)}</span></span>
              <span className="text-ink-3">收 <span style={{ color: hb.c >= hb.o ? UP : DOWN }}>{hb.c.toFixed(2)}</span></span>
              <span className="text-ink-3">低 <span className="text-ink">{hb.l.toFixed(2)}</span></span>
              {hbPct != null && (
                <span className="text-ink-3">涨跌 <span style={{ color: hbPct >= 0 ? UP : DOWN }}>{hbPct >= 0 ? "+" : ""}{hbPct.toFixed(2)}%</span></span>
              )}
              <span className="text-ink-3">量 <span className="text-ink">{(hb.v / 1e6).toFixed(1)}M</span></span>
            </div>
          </div>
        )}
      </div>

      {/* 图例 */}
      <div className="mt-1 flex items-center gap-3 px-1 font-mono text-2xs text-ink-3">
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3" style={{ background: MA5 }} />MA5</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3" style={{ background: MA20 }} />MA20</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3" style={{ background: MA60 }} />MA60</span>
        <span className="ml-auto">近 {bars.length} 根 · {data.timeframe}</span>
      </div>
    </div>
  );
}

import { useMemo } from "react";
import type { KlineData } from "@/types/analysis";

// 手绘 SVG 蜡烛图 —— 零第三方图表依赖,贴合深色量化终端风。
// A 股惯例:涨红跌绿(收 >= 开为红)。叠加 MA5/MA20/MA60 均线与成交量柱,
// 右侧标注最新价、关键支撑/压力位。
//
// 注意:SVG 的 presentation attribute(fill/stroke)里 CSS 变量 var(--x) 不生效,
// 因此这里用固定 hex 常量(与 theme.css 对齐),而非 var()。
//
// 为控制密度,默认只画最近 N 根(日 K 120 根里取尾部),避免过窄。

const UP = "#ff5b5b"; // 红(涨) —— 对齐 theme.css --up
const DOWN = "#22c07a"; // 绿(跌) —— 对齐 theme.css --down
const GRID = "#1e2836"; // --border-subtle
const AXIS = "#61728a"; // --text-muted
const MA5 = "#e8b04b";
const MA20 = "#4ba3e8";
const MA60 = "#a06be8";

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

export default function KlineChart({ data, maxBars = 80 }: Props) {
  const bars = useMemo(() => data.bars.slice(-maxBars), [data.bars, maxBars]);

  const geom = useMemo(() => {
    if (bars.length === 0) return null;
    const W = 520;
    const H = 240;
    const volH = 46;
    const padL = 6;
    const padR = 46; // 右侧留价格轴
    const padT = 8;
    const gap = 8; // 蜡烛图与量柱之间
    const priceH = H - volH - gap - padT;

    const highs = bars.map((b) => b.h);
    const lows = bars.map((b) => b.l);
    const hi = Math.max(...highs);
    const lo = Math.min(...lows);
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

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${geom.W} ${geom.H}`} className="w-full" style={{ display: "block" }}>
        {/* 价格网格线(4 条) */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => {
          const y = geom.padT + r * geom.priceH;
          const price = geom.hi - r * (geom.hi - geom.lo);
          return (
            <g key={r}>
              <line x1={geom.padL} y1={y} x2={geom.W - geom.padR} y2={y} stroke={GRID} strokeWidth={0.5} strokeDasharray="2 3" />
              <text x={geom.W - geom.padR + 3} y={y + 3} fontSize={8} fill={AXIS} fontFamily="ui-monospace, monospace">
                {price.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* 支撑/压力位标线 */}
        {support != null && (
          <g>
            <line x1={geom.padL} y1={geom.yPrice(support)} x2={geom.W - geom.padR} y2={geom.yPrice(support)} stroke={DOWN} strokeWidth={0.7} strokeDasharray="4 2" opacity={0.55} />
            <text x={geom.padL + 2} y={geom.yPrice(support) - 2} fontSize={7.5} fill={DOWN} fontFamily="ui-monospace, monospace">支撑 {support.toFixed(2)}</text>
          </g>
        )}
        {resistance != null && (
          <g>
            <line x1={geom.padL} y1={geom.yPrice(resistance)} x2={geom.W - geom.padR} y2={geom.yPrice(resistance)} stroke={UP} strokeWidth={0.7} strokeDasharray="4 2" opacity={0.55} />
            <text x={geom.padL + 2} y={geom.yPrice(resistance) - 2} fontSize={7.5} fill={UP} fontFamily="ui-monospace, monospace">压力 {resistance.toFixed(2)}</text>
          </g>
        )}

        {/* 蜡烛 + 量柱 */}
        {bars.map((b, i) => {
          const up = b.c >= b.o;
          const color = up ? UP : DOWN;
          const x = geom.cx(i);
          const yHigh = geom.yPrice(b.h);
          const yLow = geom.yPrice(b.l);
          const yO = geom.yPrice(b.o);
          const yC = geom.yPrice(b.c);
          const top = Math.min(yO, yC);
          const bodyH = Math.max(0.8, Math.abs(yC - yO));
          return (
            <g key={i}>
              {/* 影线 */}
              <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={color} strokeWidth={0.8} />
              {/* 实体 */}
              <rect x={x - geom.bodyW / 2} y={top} width={geom.bodyW} height={bodyH} fill={color} />
              {/* 量柱 */}
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
      </svg>

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

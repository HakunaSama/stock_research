import type { KlineFeatures } from "@/types/analysis";

// 技术特征摘要 —— 把后端 kline_features.py 提取的六个特征渲染成紧凑卡片组:
// 趋势 / 均线排列 / 关键价位 / 量能 / 指标(RSI·MACD) / 形态。
// 与 KlineChart 配套,放在图下方。

const DIR_LABEL: Record<string, string> = { up: "上行", down: "下行", flat: "震荡" };
const ALIGN_LABEL: Record<string, string> = { bull: "多头排列", bear: "空头排列", mixed: "缠绕" };
const VOL_LABEL: Record<string, string> = { surge: "放量", shrink: "缩量", normal: "常量" };

function fmt(v: number | null, nd = 2): string {
  return v == null ? "—" : v.toFixed(nd);
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-sm border border-subtle bg-inset px-2 py-1.5">
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="mt-0.5 font-mono text-2xs font-600 text-ink">{children}</div>
    </div>
  );
}

export default function KlineFeaturePanel({ features }: { features: KlineFeatures }) {
  const { trend, ma_state, key_levels, volume_state, indicators, patterns } = features;
  const upTone = trend.direction === "up";
  const trendColor = trend.direction === "flat" ? "var(--text-muted)" : upTone ? "var(--up)" : "var(--down)";
  const macd = indicators.macd;
  const macdRed = (macd.hist ?? 0) >= 0;

  return (
    <div className="space-y-1.5">
      {/* 趋势 + 均线排列 */}
      <div className="grid grid-cols-2 gap-1.5">
        <Cell label="趋势">
          <span style={{ color: trendColor }}>
            {DIR_LABEL[trend.direction] ?? trend.direction} · {trend.slope_pct >= 0 ? "+" : ""}
            {trend.slope_pct}%
          </span>
        </Cell>
        <Cell label="均线">
          {ALIGN_LABEL[ma_state.alignment] ?? ma_state.alignment}
          <span className="text-ink-3">
            {" "}· 价{ma_state.price_vs_ma20 === "above" ? "上" : ma_state.price_vs_ma20 === "below" ? "下" : ""}MA20
          </span>
        </Cell>
      </div>

      {/* 均线数值 */}
      <div className="grid grid-cols-4 gap-1.5">
        <Cell label="MA5">{fmt(ma_state.ma5)}</Cell>
        <Cell label="MA10">{fmt(ma_state.ma10)}</Cell>
        <Cell label="MA20">{fmt(ma_state.ma20)}</Cell>
        <Cell label="MA60">{fmt(ma_state.ma60)}</Cell>
      </div>

      {/* 关键价位 */}
      <div className="grid grid-cols-3 gap-1.5">
        <Cell label="支撑">
          <span style={{ color: "var(--down)" }}>{fmt(key_levels.support)}</span>
        </Cell>
        <Cell label="压力">
          <span style={{ color: "var(--up)" }}>{fmt(key_levels.resistance)}</span>
        </Cell>
        <Cell label="最新价">{fmt(key_levels.last_close)}</Cell>
        <Cell label="区间高">{fmt(key_levels.recent_high)}</Cell>
        <Cell label="区间低">{fmt(key_levels.recent_low)}</Cell>
        <Cell label="量能">
          {VOL_LABEL[volume_state.state] ?? volume_state.state}
          {volume_state.ratio != null && <span className="text-ink-3"> · {volume_state.ratio}x</span>}
        </Cell>
      </div>

      {/* 指标 */}
      <div className="grid grid-cols-2 gap-1.5">
        <Cell label="RSI(14)">
          <span style={{ color: (indicators.rsi14 ?? 50) >= 70 ? "var(--up)" : (indicators.rsi14 ?? 50) <= 30 ? "var(--down)" : "var(--text-primary)" }}>
            {fmt(indicators.rsi14, 1)}
          </span>
        </Cell>
        <Cell label="MACD 柱">
          <span style={{ color: macdRed ? "var(--up)" : "var(--down)" }}>
            {fmt(macd.hist, 3)}
          </span>
          <span className="text-ink-3"> · DIF {fmt(macd.dif, 3)}</span>
        </Cell>
      </div>

      {/* 形态 */}
      {patterns.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {patterns.map((p, i) => (
            <span
              key={i}
              className="rounded-sm px-1.5 py-0.5 text-2xs"
              style={{ background: "var(--amber)", color: "#ffffff", opacity: 0.9 }}
              title={p.detail}
            >
              {p.detail}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

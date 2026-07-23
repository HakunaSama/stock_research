import type { KlineData } from "@/types/analysis";

// 离线 K 线 mock —— 当后端 bridge (serve.py) 不可达时的回退数据,让脱机演示
// 仍能画出蜡烛图。真实链路走 /api/kline/<target>(vendored stocksdk 拉取的
// 真实 OHLCV);这里是形状一致的合成序列,仅用于离线兜底。
//
// 为避免手写 120 根,用一个确定性的伪随机游走生成器围绕锚定收盘价合成,
// 保证每次渲染一致(不闪烁),并大致复刻各标的的走势基调。

// 轻量确定性 PRNG(mulberry32),同一 seed 稳定复现。
function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 围绕 anchor 收盘价、按给定日均漂移合成 count 根日 K。
function synth(seed: number, count: number, endClose: number, driftPct: number): KlineData["bars"] {
  const rnd = mulberry32(seed);
  // 反推起始价:让终点约等于 endClose。
  const totalDrift = (driftPct / 100) * count;
  let price = endClose / (1 + totalDrift);
  const bars: KlineData["bars"] = [];
  const start = new Date("2026-01-22T00:00:00");
  for (let i = 0; i < count; i++) {
    const dailyDrift = driftPct / 100;
    const noise = (rnd() - 0.5) * 0.045; // ±2.25% 日内噪声
    const open = price;
    const close = Math.max(0.1, price * (1 + dailyDrift + noise));
    const high = Math.max(open, close) * (1 + rnd() * 0.02);
    const low = Math.min(open, close) * (1 - rnd() * 0.02);
    const vol = Math.round((6 + rnd() * 8) * 1e8);
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    bars.push({
      t: `${d.toISOString().slice(0, 10)} 00:00`,
      o: +open.toFixed(2),
      h: +high.toFixed(2),
      l: +low.toFixed(2),
      c: +close.toFixed(2),
      v: vol,
    });
    price = close;
  }
  return bars;
}

function build(seed: number, symbol: string, endClose: number, driftPct: number): KlineData {
  const bars = synth(seed, 120, endClose, driftPct);
  const closes = bars.map((b) => b.c);
  const ma = (n: number) =>
    closes.length >= n ? +(closes.slice(-n).reduce((s, v) => s + v, 0) / n).toFixed(2) : null;
  const last = closes[closes.length - 1];
  const lows = bars.map((b) => b.l);
  const highs = bars.map((b) => b.h);
  return {
    status: "ok",
    symbol,
    timeframe: "day",
    range: "120bars",
    bars,
    features: {
      trend: {
        direction: driftPct >= 0 ? "up" : "down",
        slope_pct: +(driftPct * 20).toFixed(2),
        since: 20,
        detail: `离线合成序列（约 ${driftPct >= 0 ? "上行" : "下行"}）`,
      },
      ma_state: {
        ma5: ma(5),
        ma10: ma(10),
        ma20: ma(20),
        ma60: ma(60),
        alignment: "mixed",
        price_vs_ma20: last >= (ma(20) ?? last) ? "above" : "below",
      },
      key_levels: {
        support: +Math.min(...lows.slice(-60)).toFixed(2),
        resistance: +Math.max(...highs.slice(-60)).toFixed(2),
        recent_high: +Math.max(...highs).toFixed(2),
        recent_low: +Math.min(...lows).toFixed(2),
        last_close: +last.toFixed(2),
      },
      volume_state: { last: bars[bars.length - 1].v, avg20: null, ratio: null, state: "normal" },
      indicators: { rsi14: null, macd: { dif: null, dea: null, hist: null } },
      patterns: [],
    },
  };
}

export const klineRuns: Record<string, KlineData> = {
  "000100": build(100, "000100", 5.16, -0.17),
  "002185": build(185, "002185", 17.69, -1.05),
};

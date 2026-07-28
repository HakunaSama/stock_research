// 数据契约 —— 研究过程(ResearchContext.research)与技术面(ctx.kline)。
// 实时行情/资讯类型见 types/market.ts;此处只保留后端研究产物的结构。

export interface DisciplineItem {
  order: number;
  text: string;
}

// ===== ODR（Open-Deep-Research）研究过程 =====
// 对齐后端 ctx.research：{engine, status, score, attempts, history, odr, sources}。
// odr 即 ODRResult.to_trace_dict()；history 为每次 attempt 的评分/重跑记录。

export interface Source {
  title: string;
  url: string;
  date: string;
}

// 一个子研究员对单个子主题的调研发现（含 think_tool 反思）。
export interface SubFinding {
  topic: string;
  notes: string;
  sources: Source[];
  tool_calls: number;
  reflections: string[];
}

// 压缩模型对单份发现的蒸馏笔记。
export interface CompressedNote {
  topic: string;
  compressed: string;
  sources: Source[];
}

// 被接受（或最优）那次 ODR 运行的完整 trace。
export interface ODRTrace {
  brief: string;
  sub_questions: string[];
  supervisor_rounds: number;
  findings: SubFinding[];
  notes: CompressedNote[];
}

// 独立 judge 对某次 attempt 的打分。
export interface JudgeVerdict {
  score: number;
  reasons: string;
  worst_gap: string;
}

// 每次 attempt 一条：分低→重跑整个 ODR，直到达标（accepted=true）。
export interface AttemptHistory {
  attempt: number;
  angle: string;
  temperature: number;
  score: number;
  accepted: boolean;
  judge: JudgeVerdict;
  supervisor_rounds: number;
  sub_topics: string[];
}

// 一只股票的整个研究过程（对齐 ctx.research）。
export interface ResearchRun {
  engine: "odr" | "legacy";
  status: "accepted" | "best_effort" | "pending";
  score: number;
  attempts: number;
  threshold: number;
  digest: string;
  sources: Source[];
  history: AttemptHistory[];
  odr: ODRTrace;
}

// ===== K 线（技术面）=====
// 对齐后端 ctx.kline：OHLCV bars + 由 kline_features.py 提取的六个技术特征。
// 数据源为 vendored stocksdk（腾讯/东财/新浪免费行情，多源故障转移）。

export interface KlineBar {
  t: string; // "2026-07-23 00:00"
  o: number;
  h: number;
  l: number;
  c: number;
  v: number; // 成交量（股）
}

export interface KlineFeatures {
  trend: { direction: "up" | "down" | "flat"; slope_pct: number; since: number; detail: string };
  ma_state: {
    ma5: number | null;
    ma10: number | null;
    ma20: number | null;
    ma60: number | null;
    alignment: "bull" | "bear" | "mixed";
    price_vs_ma20: "above" | "below" | null;
  };
  key_levels: {
    support: number | null;
    resistance: number | null;
    recent_high: number | null;
    recent_low: number | null;
    last_close: number | null;
  };
  volume_state: { last: number; avg20: number | null; ratio: number | null; state: "surge" | "shrink" | "normal" };
  indicators: { rsi14: number | null; macd: { dif: number | null; dea: number | null; hist: number | null } };
  patterns: { name: string; at: number; detail: string }[];
}

export interface KlineData {
  status: "ok" | "placeholder" | "error";
  symbol: string;
  timeframe: string;
  range: string;
  bars: KlineBar[];
  features: KlineFeatures | null;
}

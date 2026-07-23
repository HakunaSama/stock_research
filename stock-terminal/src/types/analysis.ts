// 数据契约 —— 对齐 stock_agent 的分析输出（ResearchContext.analysis）。
// 后端接入时用 adapter 把 ResearchContext 映射到这些结构即可。

export type DecisionType = "stock_pick" | "timing" | "sector" | "portfolio";

export interface Quote {
  code: string;
  name: string;
  price: number;
  changePct: number;
  changeAbs: number;
  time: string;
}

export interface Position {
  has: boolean;
  shares?: number;
  cost?: number;
  pnl?: number;
  pnlPct?: number;
  buyableAmount?: number;
  buyableShares?: number;
}

export interface Scores {
  composite: number;
  price: number;
  volume: number;
  logic: number;
  sentiment: number;
  market: number;
}

export interface Levels {
  supportLow: number;
  resistance: number;
  secondSupport: number;
  maLine: number;
  turnover: string;
  plannedBuy: string;
}

export type AttrKey = "价格" | "量能" | "逻辑" | "消息" | "大盘" | "预期";

export interface AttrRow {
  key: AttrKey;
  text: string;
  tone: "up" | "down" | "neutral" | "info";
}

export interface NewsItem {
  time: string;
  text: string;
}

export interface Verdict {
  action: string; // 推荐动作，如「推荐持有」「推荐买入」
  rating: string; // 评级标签
  rankScore: number; // 综合分（0-100）
  risk: number; // 风险分
  headline: string; // 一句话核心结论
  confidence: number; // 置信度 0-100
  tags: string[];
  ops: string; // 操作建议
  buyPoint: string; // 买点
  sellPoint: string; // 卖点
}

export type ViewTab = "推荐持有" | "最新观点" | "位置";

export interface StockAnalysis {
  id: string;
  quote: Quote;
  position: Position;
  verdict: Verdict;
  scores: Scores;
  microProgress: number; // 微观运图（蓝条）0-100
  compositeProgress: number; // 综合度（红条）0-100
  positionPct: number; // 位置%
  levels: Levels;
  attributes: AttrRow[];
  news: NewsItem[];
}

export interface WatchItem {
  code: string;
  name: string;
  price: number;
  changePct: number;
  marketCap: string;
  score: number;
  note: string;
}

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

export interface MarketSummary {
  index: string;
  indexValue: number;
  indexChangePct: number;
  time: string;
  totalPnl: number;
  totalPnlPct: number;
  positionCount: number;
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

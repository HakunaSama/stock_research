// 实时行情数据契约 —— 对齐后端 stock_agent/market.py 的 JSON 输出。
// 全部字段来自真实上游（腾讯/东财/新浪行情 + 东财资讯），无本地编造数据。

export interface StockQuote {
  symbol: string; // 归一化代码，如 "sh600519"
  code: string; // 纯数字代码
  name: string;
  price: number;
  prev_close: number;
  open: number;
  high: number;
  low: number;
  volume: number; // 股
  amount: number; // 元
  change: number;
  change_pct: number; // 百分数值，如 -1.13
  turnover_rate: number | null; // 换手率 %
  pe_ttm: number | null;
  pb: number | null;
  total_market_cap: number | null; // 元
  float_market_cap: number | null; // 元
  time: string; // 交易所时间 "YYYY-MM-DD HH:mm:ss"
  source: string;
}

export interface SearchHit {
  symbol: string;
  code: string;
  name: string;
  market: string; // sh / sz / bj
  type: string; // GP-A 等
}

export interface NewsArticle {
  title: string;
  summary: string;
  source: string;
  date: string;
  url: string;
}

// /api/runs 的条目 —— 哪些标的已有 AI 深度研究产物。
export interface RunSummary {
  target: string;
  run_id: string;
  engine: string;
  status: string;
  score: number;
  attempts: number;
  threshold: number;
  kline_status: string;
}

// 自选池条目（本地持久化；name 为兜底显示，行情返回后以行情 name 为准）。
export interface WatchEntry {
  code: string;
  name: string;
}

export type KlinePeriod = "day" | "week" | "month" | "60m";

// 全市场榜单条目（东财实时列表；停牌股部分字段为 null）。
export interface RankItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null; // 手
  amount: number | null; // 元
  turnover_rate: number | null;
  total_market_cap: number | null;
}

export type RankKind = "pct_desc" | "pct_asc" | "amount" | "turnover";

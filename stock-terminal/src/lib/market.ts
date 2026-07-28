// 实时行情 API 客户端 —— 报价/指数/搜索/实时K线/个股资讯/研究产物清单。
// 与 lib/api.ts（研究过程详情）互补；所有请求带 cookie，超时快速失败。

import { API_BASE, adaptKline } from "@/lib/api";
import type { KlineData } from "@/types/analysis";
import type {
  KlinePeriod,
  NewsArticle,
  RankItem,
  RankKind,
  RunSummary,
  SearchHit,
  StockQuote,
} from "@/types/market";

async function getJSON<T>(path: string, timeoutMs = 6000): Promise<T | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      signal: ctrl.signal,
      credentials: "include",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// 批量实时报价。失败返回 []（调用方保留上一次数据，避免闪空）。
export async function fetchQuotes(codes: string[]): Promise<StockQuote[]> {
  if (codes.length === 0) return [];
  const data = await getJSON<StockQuote[]>(
    `/api/quotes?symbols=${encodeURIComponent(codes.join(","))}`,
  );
  return Array.isArray(data) ? data : [];
}

// 大盘指数（上证/深证成指/创业板指/沪深300）。
export async function fetchIndices(): Promise<StockQuote[]> {
  const data = await getJSON<StockQuote[]>("/api/market/indices");
  return Array.isArray(data) ? data : [];
}

// 代码/名称/拼音搜索 A 股。
export async function searchStocks(keyword: string): Promise<SearchHit[]> {
  const kw = keyword.trim();
  if (!kw) return [];
  const data = await getJSON<SearchHit[]>(
    `/api/market/search?q=${encodeURIComponent(kw)}`,
  );
  return Array.isArray(data) ? data : [];
}

// 任意标的的实时 K 线（不依赖研究产物）。60m 映射后端分钟线。
export async function fetchLiveKline(
  code: string,
  period: KlinePeriod = "day",
  count = 180,
): Promise<KlineData | null> {
  const raw = await getJSON<Parameters<typeof adaptKline>[0]>(
    `/api/market/kline/${encodeURIComponent(code)}?period=${period}&count=${count}`,
  );
  if (!raw) return null;
  const data = adaptKline(raw);
  return data.status === "ok" && data.bars.length > 0 ? data : null;
}

// 全市场榜单（涨幅/跌幅/成交额/换手率），东财实时列表。
export async function fetchRank(kind: RankKind, limit = 30): Promise<RankItem[]> {
  const data = await getJSON<RankItem[]>(
    `/api/market/rank?kind=${kind}&limit=${limit}`,
  );
  return Array.isArray(data) ? data : [];
}

// 个股资讯（东财公开接口，真实新闻）。
export async function fetchNews(code: string): Promise<NewsArticle[]> {
  const data = await getJSON<NewsArticle[]>(
    `/api/news/${encodeURIComponent(code)}`,
  );
  return Array.isArray(data) ? data : [];
}

// 已有 AI 研究产物的标的清单。
export async function fetchRuns(): Promise<RunSummary[]> {
  const data = await getJSON<RunSummary[]>("/api/runs");
  return Array.isArray(data) ? data : [];
}

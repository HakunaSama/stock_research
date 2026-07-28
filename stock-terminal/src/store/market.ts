// 全局市场状态 —— 自选池（本地持久化）、实时行情轮询、研究产物索引、
// 选中标的与研究抽屉。所有行情数据来自后端真实数据源，失败时保留上次快照。

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { fetchIndices, fetchQuotes, fetchRuns } from "@/lib/market";
import type { RunSummary, StockQuote, WatchEntry } from "@/types/market";

// 默认自选池 —— 全部为真实 A 股代码，首次使用时的起始清单，用户可增删。
const DEFAULT_WATCHLIST: WatchEntry[] = [
  { code: "000100", name: "TCL科技" },
  { code: "002185", name: "华天科技" },
  { code: "600519", name: "贵州茅台" },
  { code: "600030", name: "中信证券" },
  { code: "601012", name: "隆基绿能" },
  { code: "601899", name: "紫金矿业" },
  { code: "600900", name: "长江电力" },
  { code: "601088", name: "中国神华" },
  { code: "601398", name: "工商银行" },
  { code: "600585", name: "海螺水泥" },
  { code: "002202", name: "金风科技" },
  { code: "600104", name: "上汽集团" },
];

export type WatchSort = "default" | "pctDesc" | "pctAsc";

interface MarketState {
  // ----- 自选池（持久化） -----
  watchlist: WatchEntry[];
  addStock: (entry: WatchEntry) => void;
  removeStock: (code: string) => void;

  // ----- 实时行情 -----
  quotes: Record<string, StockQuote>; // key: 纯数字 code
  indices: StockQuote[];
  lastUpdated: number | null; // 最近一次行情成功刷新的时间戳(ms)
  refreshMarket: () => Promise<void>;

  // ----- AI 研究产物 -----
  runs: Record<string, RunSummary>; // key: target code
  refreshRuns: () => Promise<void>;

  // ----- 选中与研究抽屉 -----
  selectedCode: string;
  select: (code: string) => void;
  researchOpenCode: string | null;
  openResearch: (code: string) => void;
  closeResearch: () => void;

  // ----- 排序 -----
  sort: WatchSort;
  setSort: (s: WatchSort) => void;
}

export const useMarket = create<MarketState>()(
  persist(
    (set, get) => ({
      watchlist: DEFAULT_WATCHLIST,
      addStock: (entry) => {
        const { watchlist, select } = get();
        if (!watchlist.some((w) => w.code === entry.code)) {
          set({ watchlist: [entry, ...watchlist] });
          // 新加入的标的立即拉一次行情，避免等下一个轮询周期
          void get().refreshMarket();
        }
        select(entry.code);
      },
      removeStock: (code) => {
        const { watchlist, selectedCode } = get();
        const next = watchlist.filter((w) => w.code !== code);
        set({ watchlist: next });
        if (selectedCode === code && next.length > 0) {
          set({ selectedCode: next[0].code });
        }
      },

      quotes: {},
      indices: [],
      lastUpdated: null,
      refreshMarket: async () => {
        const { watchlist, selectedCode } = get();
        const codes = watchlist.map((w) => w.code);
        if (selectedCode && !codes.includes(selectedCode)) codes.push(selectedCode);
        const [quotes, indices] = await Promise.all([
          fetchQuotes(codes),
          fetchIndices(),
        ]);
        if (quotes.length === 0 && indices.length === 0) return; // 失败保留旧快照
        set((s) => ({
          quotes: {
            ...s.quotes,
            ...Object.fromEntries(quotes.map((q) => [q.code, q])),
          },
          indices: indices.length > 0 ? indices : s.indices,
          lastUpdated: Date.now(),
        }));
      },

      runs: {},
      refreshRuns: async () => {
        const list = await fetchRuns();
        set({ runs: Object.fromEntries(list.map((r) => [r.target, r])) });
      },

      selectedCode: DEFAULT_WATCHLIST[0].code,
      select: (code) => {
        set({ selectedCode: code });
        // 立即拉一次行情，让榜单/搜索里选中的非自选股即刻有报价
        void get().refreshMarket();
      },
      researchOpenCode: null,
      openResearch: (code) => set({ researchOpenCode: code, selectedCode: code }),
      closeResearch: () => set({ researchOpenCode: null }),

      sort: "default",
      setSort: (s) => set({ sort: s }),
    }),
    {
      name: "stock-terminal-market",
      // 只持久化用户资产（自选池/选中/排序）；行情快照每次会话重新拉取。
      partialize: (s) => ({
        watchlist: s.watchlist,
        selectedCode: s.selectedCode,
        sort: s.sort,
      }),
    },
  ),
);

// ----- 行情轮询：单例 interval，页面隐藏时暂停 -----
const POLL_MS = 5000;
let pollTimer: ReturnType<typeof setInterval> | null = null;

export function startMarketPolling(): () => void {
  const tick = () => {
    if (document.hidden) return;
    void useMarket.getState().refreshMarket();
  };
  void useMarket.getState().refreshMarket();
  void useMarket.getState().refreshRuns();
  if (pollTimer == null) {
    pollTimer = setInterval(tick, POLL_MS);
  }
  return () => {
    if (pollTimer != null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };
}

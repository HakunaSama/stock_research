import { create } from "zustand";
import { stocks } from "@/data/stocks";

// 已完成深度研究的股票 id 集合（当前由本地 stocks 数据决定；接后端后可动态填充）。
export const researchedIds = new Set(stocks.map((s) => s.id));

interface TerminalState {
  selectedId: string;
  select: (id: string) => void;
  // ODR 研究过程抽屉：为空表示关闭，否则为要展示的股票 id。
  researchOpenId: string | null;
  openResearch: (id: string) => void;
  closeResearch: () => void;
}

export const useTerminal = create<TerminalState>((set) => ({
  selectedId: stocks[0]?.id ?? "",
  select: (id) => set({ selectedId: id }),
  researchOpenId: null,
  openResearch: (id) => set({ researchOpenId: id, selectedId: id }),
  closeResearch: () => set({ researchOpenId: null }),
}));

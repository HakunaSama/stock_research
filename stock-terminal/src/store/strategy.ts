// 策略库全局状态 —— 抽屉开关 + 策略列表缓存 + CRUD/激活动作。
// ResearchCard 读取「当前激活策略名」，TopBar 菜单与研究卡都能打开抽屉。

import { create } from "zustand";
import {
  activateStrategy,
  createStrategy,
  deleteStrategy,
  fetchStrategies,
  publishStrategy,
  updateStrategy,
  type BuiltinStrategy,
  type Strategy,
} from "@/lib/strategy";

interface StrategyState {
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;

  loaded: boolean;
  loading: boolean;
  activeId: number; // 0 = 内置示例
  builtin: BuiltinStrategy | null;
  strategies: Strategy[];

  refresh: () => Promise<void>;
  ensureLoaded: () => void;
  create: (payload: {
    name: string;
    rawText: string;
    summary?: string;
    tags?: string[];
    activate: boolean;
  }) => Promise<void>;
  update: (payload: {
    id: number;
    name: string;
    rawText: string;
    summary?: string;
    tags?: string[];
  }) => Promise<void>;
  remove: (id: number) => Promise<void>;
  activate: (id: number) => Promise<void>;
  publish: (id: number, isPublic: boolean, summary?: string, tags?: string[]) => Promise<void>;
}

export const useStrategies = create<StrategyState>()((set, get) => ({
  drawerOpen: false,
  openDrawer: () => {
    set({ drawerOpen: true });
    void get().refresh();
  },
  closeDrawer: () => set({ drawerOpen: false }),

  loaded: false,
  loading: false,
  activeId: 0,
  builtin: null,
  strategies: [],

  refresh: async () => {
    if (get().loading) return;
    set({ loading: true });
    try {
      const data = await fetchStrategies();
      set({
        activeId: data.active_id,
        builtin: data.builtin,
        strategies: data.strategies,
        loaded: true,
      });
    } catch {
      // 未登录或后端不可用 —— 保持现状，UI 各自降级
    } finally {
      set({ loading: false });
    }
  },

  ensureLoaded: () => {
    if (!get().loaded && !get().loading) void get().refresh();
  },

  create: async ({ name, rawText, summary = "", tags = [], activate }) => {
    await createStrategy({ name, raw_text: rawText, summary, tags, activate });
    await get().refresh();
  },

  update: async ({ id, name, rawText, summary = "", tags = [] }) => {
    await updateStrategy(id, { name, raw_text: rawText, summary, tags });
    await get().refresh();
  },

  remove: async (id) => {
    await deleteStrategy(id);
    await get().refresh();
  },

  activate: async (id) => {
    await activateStrategy(id);
    await get().refresh();
  },

  publish: async (id, isPublic, summary, tags) => {
    await publishStrategy(id, { is_public: isPublic, summary, tags });
    await get().refresh();
  },
}));

/** 当前激活策略的展示名（未加载时给通用占位）。 */
export function activeStrategyName(s: StrategyState): string {
  if (!s.loaded) return "…";
  if (s.activeId === 0) return s.builtin?.name ?? "内置示例";
  return s.strategies.find((x) => x.id === s.activeId)?.name ?? "内置示例";
}

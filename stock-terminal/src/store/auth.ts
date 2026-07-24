// 全局鉴权状态 —— 当前登录用户 + 功能开关 + 钱包余额。
// 应用启动时 bootstrap() 拉一次 /me 和 /config;登录/登出后刷新。
// 钱包在登录后按需 refreshWallet(),充值/扣费后也主动刷新。

import { create } from "zustand";
import type { AppConfig, PublicUser, Wallet } from "@/lib/auth";
import {
  fetchConfig,
  fetchMe,
  fetchWallet,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
} from "@/lib/auth";

interface AuthState {
  user: PublicUser | null;
  config: AppConfig;
  wallet: Wallet | null;
  ready: boolean; // 首次 bootstrap 是否完成(避免闪烁登录页)
  bootstrap: () => Promise<void>;
  refreshWallet: () => Promise<void>;
  login: (u: string, p: string) => Promise<void>;
  register: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  config: { research_enabled: false, daily_quota: 0, research_cost: 1, payment_provider: "stub" },
  wallet: null,
  ready: false,
  bootstrap: async () => {
    const [user, config] = await Promise.all([fetchMe(), fetchConfig()]);
    const wallet = user ? await fetchWallet() : null;
    set({ user, config, wallet, ready: true });
  },
  refreshWallet: async () => {
    const wallet = await fetchWallet();
    set({ wallet });
  },
  login: async (u, p) => {
    const user = await apiLogin(u, p);
    const wallet = await fetchWallet();
    set({ user, wallet });
  },
  register: async (u, p) => {
    const user = await apiRegister(u, p);
    const wallet = await fetchWallet();
    set({ user, wallet });
  },
  logout: async () => {
    await apiLogout();
    set({ user: null, wallet: null });
  },
}));

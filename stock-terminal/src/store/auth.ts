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
  login: (account: string, password: string) => Promise<void>;
  register: (email: string, code: string, password: string, username?: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: PublicUser) => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  config: {
    research_enabled: false,
    daily_quota: 0,
    sub_daily_quota: 0,
    research_cost: 1,
    payment_provider: "stub",
    email_dev_mode: false,
  },
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
  login: async (account, password) => {
    const user = await apiLogin(account, password);
    const wallet = await fetchWallet();
    set({ user, wallet });
  },
  register: async (email, code, password, username = "") => {
    const user = await apiRegister(email, code, password, username);
    const wallet = await fetchWallet();
    set({ user, wallet });
  },
  logout: async () => {
    await apiLogout();
    set({ user: null, wallet: null });
  },
  // 绑定邮箱等操作后原地更新用户信息。
  setUser: (user) => set({ user }),
}));

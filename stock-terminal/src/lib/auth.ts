// 鉴权 + 研究任务 API —— 与后端 webapp (FastAPI) 对接。
// 所有请求都带 credentials:"include",让 HTTP-only session cookie 随行。
// 生产同源(nginx 反代 /api),本地 dev 用 VITE_RESEARCH_API 指向后端。

import { API_BASE } from "@/lib/api";

export interface PublicUser {
  id: number;
  username: string;
  is_admin: boolean;
}

export interface AppConfig {
  research_enabled: boolean;
  daily_quota: number;
  research_cost: number;
  payment_provider: string;
}

export interface Wallet {
  balance: number;
  total_topup: number;
  total_spent: number;
  free_left: number;
  daily_quota: number;
  research_cost: number;
}

export interface Plan {
  code: string;
  name: string;
  kind: "pack" | "monthly";
  credits: number;
  amount_cents: number;
  desc: string;
}

export interface LedgerEntry {
  id: number;
  user_id: number;
  amount: number;
  balance_after: number;
  reason: string;
  ref_type: string;
  ref_id: string;
  memo: string;
  created_at: number;
}

export interface Order {
  id: number;
  out_trade_no: string;
  user_id: number;
  plan_code: string;
  credits: number;
  amount_cents: number;
  channel: string;
  status: "pending" | "paid" | "closed" | "refunded";
  channel_txid: string;
  created_at: number;
  paid_at: number | null;
}

export interface PaymentIntent {
  provider: string;
  out_trade_no: string;
  amount_cents: number;
  credits: number;
  pay_url: string;
  qr_url: string;
  auto_confirm: boolean;
  plan: Plan;
  status: string;
}

export interface ResearchJob {
  id: number;
  target: string;
  question: string;
  status: "pending" | "running" | "done" | "failed";
  run_id: string;
  error: string;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
}

// 统一请求封装:JSON body、带 cookie、把后端 detail 作为错误抛出。
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function register(username: string, password: string): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function login(username: string, password: string): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
}

// 拉当前登录用户;未登录(401)返回 null,不抛错。
export async function fetchMe(): Promise<PublicUser | null> {
  try {
    return await req<PublicUser>("/api/auth/me");
  } catch {
    return null;
  }
}

// 读功能开关(是否开启在线研究、每日配额、单次点数成本、支付渠道)。失败给保守缺省。
export async function fetchConfig(): Promise<AppConfig> {
  try {
    return await req<AppConfig>("/api/config");
  } catch {
    return { research_enabled: false, daily_quota: 0, research_cost: 1, payment_provider: "stub" };
  }
}

export function startResearch(target: string, question = ""): Promise<ResearchJob> {
  return req<ResearchJob>("/api/research/start", {
    method: "POST",
    body: JSON.stringify({ target, question }),
  });
}

export function fetchJobs(): Promise<ResearchJob[]> {
  return req<ResearchJob[]>("/api/research/jobs");
}

// --- 钱包 / 充值 ---

export async function fetchWallet(): Promise<Wallet | null> {
  try {
    return await req<Wallet>("/api/wallet");
  } catch {
    return null;
  }
}

export function fetchLedger(): Promise<LedgerEntry[]> {
  return req<LedgerEntry[]>("/api/wallet/ledger");
}

export function fetchPlans(): Promise<{ plans: Plan[]; provider: string }> {
  return req<{ plans: Plan[]; provider: string }>("/api/plans");
}

export function createOrder(planCode: string): Promise<PaymentIntent> {
  return req<PaymentIntent>("/api/orders", {
    method: "POST",
    body: JSON.stringify({ plan_code: planCode }),
  });
}

export function fetchOrders(): Promise<Order[]> {
  return req<Order[]>("/api/orders");
}

// 占位支付渠道:模拟支付成功(真实渠道通过异步回调结算,不走这里)。
export function simulatePayment(
  outTradeNo: string,
): Promise<{ ok: boolean; balance: number; order: Order }> {
  return req<{ ok: boolean; balance: number; order: Order }>(
    `/api/orders/${outTradeNo}/simulate`,
    { method: "POST" },
  );
}

// --- 后台管理(仅 admin) ---

export interface AdminStats {
  total_users: number;
  total_jobs: number;
  jobs_today: number;
  jobs_running: number;
  paid_orders: number;
  revenue_cents: number;
  revenue_today_cents: number;
  credits_outstanding: number;
}

export interface AdminUser {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: number;
  balance: number;
  total_topup: number;
  total_spent: number;
}

export function adminFetchStats(): Promise<AdminStats> {
  return req<AdminStats>("/api/admin/stats");
}

export function adminFetchUsers(): Promise<AdminUser[]> {
  return req<AdminUser[]>("/api/admin/users");
}

export function adminAdjustCredits(
  userId: number,
  delta: number,
  memo = "",
): Promise<{ user_id: number; balance: number }> {
  return req<{ user_id: number; balance: number }>(`/api/admin/users/${userId}/credits`, {
    method: "POST",
    body: JSON.stringify({ delta, memo }),
  });
}

export function adminSetAdmin(
  userId: number,
  isAdmin: boolean,
): Promise<{ user_id: number; is_admin: boolean }> {
  return req<{ user_id: number; is_admin: boolean }>(`/api/admin/users/${userId}/admin`, {
    method: "POST",
    body: JSON.stringify({ is_admin: isAdmin }),
  });
}

export function adminFetchOrders(status?: string): Promise<Order[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return req<Order[]>(`/api/admin/orders${q}`);
}

export function adminFetchLedger(): Promise<LedgerEntry[]> {
  return req<LedgerEntry[]>("/api/admin/ledger");
}

// 鉴权 + 研究任务 API —— 与后端 webapp (FastAPI) 对接。
// 所有请求都带 credentials:"include",让 HTTP-only session cookie 随行。
// 生产同源(nginx 反代 /api),本地 dev 用 VITE_RESEARCH_API 指向后端。

import { API_BASE } from "@/lib/api";

export interface PublicUser {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  is_admin: boolean;
  display_name: string;
  bio: string;
  avatar_url: string;
  created_at: number;
  last_login_at: number | null;
}

export interface ActiveSession {
  id: string;
  current: boolean;
  created_at: number;
  expires_at: number;
  last_seen_at: number;
  user_agent: string;
  ip_address: string;
}

export interface AppConfig {
  research_enabled: boolean;
  daily_quota: number;
  sub_daily_quota: number;
  research_cost: number;
  payment_provider: string;
  email_dev_mode: boolean; // SMTP 未配置:验证码直接回显(仅开发环境)
}

export interface Wallet {
  balance: number;
  total_topup: number;
  total_spent: number;
  free_left: number;
  daily_quota: number;
  research_cost: number;
  sub_active: boolean;
  sub_expires_at: number | null;
  sub_plan_code: string;
}

export interface Plan {
  code: string;
  name: string;
  kind: "pack" | "monthly";
  credits: number;
  days?: number; // monthly 套餐赠送的会员天数
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
  strategy_id: number;
  strategy_name: string;
}

// 统一请求封装:JSON body、带 cookie、把后端 detail 作为错误抛出。
export async function req<T>(path: string, init?: RequestInit): Promise<T> {
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

export type CodePurpose = "register" | "reset" | "bind";

export interface SendCodeResult {
  ok: boolean;
  ttl_seconds: number;
  resend_after: number;
  dev_code?: string; // 仅开发模式(未配置 SMTP)返回
}

// 发送邮箱验证码(注册 / 找回密码 / 绑定邮箱)。
export function sendEmailCode(email: string, purpose: CodePurpose): Promise<SendCodeResult> {
  return req<SendCodeResult>("/api/auth/send-code", {
    method: "POST",
    body: JSON.stringify({ email, purpose }),
  });
}

// 邮箱注册:邮箱 + 验证码 + 密码(用户名可选,缺省由邮箱前缀生成)。
export function register(
  email: string,
  code: string,
  password: string,
  username = "",
): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, code, password, username }),
  });
}

// 登录:account 可以是邮箱或用户名。
export function login(account: string, password: string): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ account, password }),
  });
}

// 找回密码:邮箱 + 验证码 + 新密码;成功后所有会话失效,需重新登录。
export function resetPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });
}

// 修改密码(已登录):校验原密码,踢掉除当前外的其他会话。
export function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}

// 绑定 / 换绑邮箱(已登录,老账号补绑用)。
export function bindEmail(email: string, code: string): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/bind-email", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export function updateProfile(input: {
  username: string;
  display_name: string;
  bio: string;
  current_password?: string;
}): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/profile", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function uploadAvatar(file: File): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/avatar", {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
}

export function deleteAvatar(): Promise<PublicUser> {
  return req<PublicUser>("/api/auth/avatar", { method: "DELETE" });
}

export function fetchSessions(): Promise<ActiveSession[]> {
  return req<ActiveSession[]>("/api/auth/sessions");
}

export function revokeSession(sessionId: string): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/api/auth/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export function revokeOtherSessions(): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>("/api/auth/sessions/revoke-others", { method: "POST" });
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
    return {
      research_enabled: false,
      daily_quota: 0,
      sub_daily_quota: 0,
      research_cost: 1,
      payment_provider: "stub",
      email_dev_mode: false,
    };
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
  active_subscriptions: number;
  verified_users: number;
  disabled_users: number;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  disabled: boolean;
  is_admin: boolean;
  created_at: number;
  balance: number;
  total_topup: number;
  total_spent: number;
  sub_expires_at: number | null;
}

export function adminFetchStats(): Promise<AdminStats> {
  return req<AdminStats>("/api/admin/stats");
}

export function adminFetchUsers(q = ""): Promise<AdminUser[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return req<AdminUser[]>(`/api/admin/users${qs}`);
}

// 禁用 / 解禁账号(禁用会立刻踢下线)。
export function adminSetDisabled(
  userId: number,
  disabled: boolean,
): Promise<{ user_id: number; disabled: boolean }> {
  return req<{ user_id: number; disabled: boolean }>(`/api/admin/users/${userId}/disabled`, {
    method: "POST",
    body: JSON.stringify({ disabled }),
  });
}

// 手动赠送会员天数(站外打赏兑换等场景)。
export function adminGrantMembership(
  userId: number,
  days: number,
  memo = "",
): Promise<{ user_id: number; sub_expires_at: number; days_added: number }> {
  return req<{ user_id: number; sub_expires_at: number; days_added: number }>(
    `/api/admin/users/${userId}/membership`,
    { method: "POST", body: JSON.stringify({ days, memo }) },
  );
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

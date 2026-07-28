import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// A股习惯：涨=红(up) 跌=绿(down)。返回对应 CSS 变量色。
export function dirColor(v: number): string {
  if (v > 0) return "var(--up)";
  if (v < 0) return "var(--down)";
  return "var(--text-secondary)";
}

export function signPct(v: number): string {
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%`;
}

export function signNum(v: number, digits = 2): string {
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}`;
}

export function fmtMoney(v: number): string {
  return v.toLocaleString("zh-CN");
}

// 成交量（股）→ "1.2亿手" / "342万手" / "5600手"。A股 1手 = 100股。
export function fmtVolume(shares: number): string {
  const lots = shares / 100;
  if (lots >= 1e8) return `${(lots / 1e8).toFixed(2)}亿手`;
  if (lots >= 1e4) return `${(lots / 1e4).toFixed(1)}万手`;
  return `${Math.round(lots).toLocaleString("zh-CN")}手`;
}

// 金额（元）→ "12.4亿" / "3560万"。用于成交额/市值。
export function fmtAmountCn(yuan: number | null | undefined): string {
  if (yuan == null || !isFinite(yuan) || yuan === 0) return "-";
  if (yuan >= 1e12) return `${(yuan / 1e12).toFixed(2)}万亿`;
  if (yuan >= 1e8) return `${(yuan / 1e8).toFixed(1)}亿`;
  if (yuan >= 1e4) return `${(yuan / 1e4).toFixed(0)}万`;
  return yuan.toFixed(0);
}

// 可空数值 → 固定小数（空则 "-"）。行情里 pe/pb/换手率可能缺失。
export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || !isFinite(v)) return "-";
  return v.toFixed(digits);
}

// 整数分 → "¥12.34" 人民币展示。金额在后端统一用整数分,避免浮点误差。
export function fmtCents(cents: number): string {
  return `¥${(cents / 100).toFixed(2)}`;
}

// Unix 秒时间戳 → 本地日期时间字符串。
export function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

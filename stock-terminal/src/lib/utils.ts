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

// 整数分 → "¥12.34" 人民币展示。金额在后端统一用整数分,避免浮点误差。
export function fmtCents(cents: number): string {
  return `¥${(cents / 100).toFixed(2)}`;
}

// Unix 秒时间戳 → 本地日期时间字符串。
export function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

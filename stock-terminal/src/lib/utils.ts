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

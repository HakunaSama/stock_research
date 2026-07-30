// 策略库 API —— 用户自然语言策略的增删改查与激活（策略热插拔）。
// 后端在发起研究时把「当前激活策略」交给管线的策略编译器逐条核对；
// id=0 恒指内置示例策略（不可编辑，作为未设置时的回退）。

import { req } from "@/lib/auth";

export interface Strategy {
  id: number;
  name: string;
  raw_text: string;
  is_active: boolean;
  created_at: number;
  updated_at: number;
}

export interface BuiltinStrategy {
  id: 0;
  name: string;
  raw_text: string;
}

export interface StrategyList {
  active_id: number; // 0 = 内置示例
  builtin: BuiltinStrategy;
  strategies: Strategy[];
}

export function fetchStrategies(): Promise<StrategyList> {
  return req<StrategyList>("/api/strategies");
}

export function createStrategy(
  name: string,
  rawText: string,
  activate = false,
): Promise<Strategy> {
  return req<Strategy>("/api/strategies", {
    method: "POST",
    body: JSON.stringify({ name, raw_text: rawText, activate }),
  });
}

export function updateStrategy(
  id: number,
  name: string,
  rawText: string,
  activate = false,
): Promise<Strategy> {
  return req<Strategy>(`/api/strategies/${id}`, {
    method: "PUT",
    body: JSON.stringify({ name, raw_text: rawText, activate }),
  });
}

export function deleteStrategy(id: number): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/api/strategies/${id}`, { method: "DELETE" });
}

export function activateStrategy(id: number): Promise<{ ok: boolean; active_id: number }> {
  return req<{ ok: boolean; active_id: number }>(`/api/strategies/${id}/activate`, {
    method: "POST",
  });
}

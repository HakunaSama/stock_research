// 策略库 + 策略大厅 API
// 个人库：增删改查 / 激活 / 发布到大厅
// 大厅：浏览 / 标签 / 点赞 / 收藏 / 评论 / 采用到自己的库

import { req } from "@/lib/auth";

export interface Strategy {
  id: number;
  name: string;
  raw_text: string;
  summary: string;
  tags: string[];
  is_active: boolean;
  is_public: boolean;
  like_count: number;
  favorite_count: number;
  comment_count: number;
  published_at: number | null;
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

export interface HallStrategy {
  id: number;
  user_id: number;
  author_name: string;
  name: string;
  summary: string;
  raw_text: string;
  tags: string[];
  like_count: number;
  favorite_count: number;
  comment_count: number;
  liked: boolean;
  favorited: boolean;
  published_at: number | null;
  created_at: number;
  updated_at: number;
  is_owner: boolean;
}

export interface HallComment {
  id: number;
  user_id: number;
  username: string;
  body: string;
  created_at: number;
  is_mine: boolean;
}

export type HallSort = "hot" | "new" | "likes" | "comments";

export function fetchStrategies(): Promise<StrategyList> {
  return req<StrategyList>("/api/strategies");
}

export function createStrategy(payload: {
  name: string;
  raw_text: string;
  summary?: string;
  tags?: string[];
  activate?: boolean;
}): Promise<Strategy> {
  return req<Strategy>("/api/strategies", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      raw_text: payload.raw_text,
      summary: payload.summary ?? "",
      tags: payload.tags ?? [],
      activate: payload.activate ?? false,
    }),
  });
}

export function updateStrategy(
  id: number,
  payload: {
    name: string;
    raw_text: string;
    summary?: string;
    tags?: string[];
    activate?: boolean;
  },
): Promise<Strategy> {
  return req<Strategy>(`/api/strategies/${id}`, {
    method: "PUT",
    body: JSON.stringify({
      name: payload.name,
      raw_text: payload.raw_text,
      summary: payload.summary ?? "",
      tags: payload.tags ?? [],
      activate: payload.activate ?? false,
    }),
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

export function publishStrategy(
  id: number,
  payload: { is_public: boolean; summary?: string; tags?: string[] },
): Promise<Strategy> {
  return req<Strategy>(`/api/strategies/${id}/publish`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchHallStrategies(params: {
  tag?: string;
  q?: string;
  sort?: HallSort;
  limit?: number;
  offset?: number;
}): Promise<{ items: HallStrategy[]; sort: string; tag: string; q: string }> {
  const sp = new URLSearchParams();
  if (params.tag) sp.set("tag", params.tag);
  if (params.q) sp.set("q", params.q);
  if (params.sort) sp.set("sort", params.sort);
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  return req(`/api/hall/strategies${qs ? `?${qs}` : ""}`);
}

export function fetchHallStrategy(id: number): Promise<HallStrategy> {
  return req<HallStrategy>(`/api/hall/strategies/${id}`);
}

export function fetchHallTags(): Promise<{ tags: { tag: string; count: number }[] }> {
  return req("/api/hall/tags");
}

export function fetchMyFavorites(): Promise<{ items: HallStrategy[] }> {
  return req("/api/hall/favorites");
}

export function toggleHallLike(
  id: number,
): Promise<{ liked: boolean; like_count: number }> {
  return req(`/api/hall/strategies/${id}/like`, { method: "POST" });
}

export function toggleHallFavorite(
  id: number,
): Promise<{ favorited: boolean; favorite_count: number }> {
  return req(`/api/hall/strategies/${id}/favorite`, { method: "POST" });
}

export function fetchHallComments(id: number): Promise<{ comments: HallComment[] }> {
  return req(`/api/hall/strategies/${id}/comments`);
}

export function postHallComment(id: number, body: string): Promise<{ id: number; ok: boolean }> {
  return req(`/api/hall/strategies/${id}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function deleteHallComment(id: number): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/api/hall/comments/${id}`, { method: "DELETE" });
}

export function adoptHallStrategy(
  id: number,
  activate = false,
): Promise<{ ok: boolean; strategy_id: number }> {
  return req(`/api/hall/strategies/${id}/adopt`, {
    method: "POST",
    body: JSON.stringify({ activate }),
  });
}

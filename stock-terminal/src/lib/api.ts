// 后端桥接 —— 从 stock-research-agent 的 HTTP bridge (serve.py) 拉取真实
// context.json 里的 research 槽,映射成前端的 ResearchRun。
//
// 服务端点(见 stock-research-agent/serve.py):
//   GET /api/research/<target>  -> ResearchSlot(含 engine/status/score/attempts/
//                                   threshold/digest/sources/history/odr)
//
// 设计为「渐进增强」:拿不到(服务没起/404/网络错)就返回 null,调用方回退
// 到 data/research.ts 的本地 mock —— 脱机也能完整演示。

import type {
  ResearchRun,
  AttemptHistory,
  ODRTrace,
  Source,
  SubFinding,
  CompressedNote,
  KlineData,
  KlineBar,
  KlineFeatures,
} from "@/types/analysis";

// 后端地址可通过 Vite 环境变量覆盖(VITE_RESEARCH_API);默认打本地 bridge。
const API_BASE: string =
  (import.meta.env.VITE_RESEARCH_API as string | undefined) ?? "http://127.0.0.1:8787";

// 后端 research 槽的原始形状(容错:字段可能缺失)。
interface RawResearch {
  engine?: string;
  status?: string;
  score?: number;
  attempts?: number;
  threshold?: number;
  digest?: string;
  sources?: unknown[];
  history?: unknown[];
  odr?: Record<string, unknown>;
}

function asSources(v: unknown): Source[] {
  if (!Array.isArray(v)) return [];
  return v.map((s) => {
    const o = (s ?? {}) as Record<string, unknown>;
    return {
      title: String(o.title ?? ""),
      url: String(o.url ?? ""),
      date: String(o.date ?? ""),
    };
  });
}

function asFindings(v: unknown): SubFinding[] {
  if (!Array.isArray(v)) return [];
  return v.map((f) => {
    const o = (f ?? {}) as Record<string, unknown>;
    return {
      topic: String(o.topic ?? ""),
      notes: String(o.notes ?? ""),
      sources: asSources(o.sources),
      tool_calls: Number(o.tool_calls ?? 0),
      reflections: Array.isArray(o.reflections) ? o.reflections.map(String) : [],
    };
  });
}

function asNotes(v: unknown): CompressedNote[] {
  if (!Array.isArray(v)) return [];
  return v.map((n) => {
    const o = (n ?? {}) as Record<string, unknown>;
    return {
      topic: String(o.topic ?? ""),
      compressed: String(o.compressed ?? ""),
      sources: asSources(o.sources),
    };
  });
}

function asHistory(v: unknown): AttemptHistory[] {
  if (!Array.isArray(v)) return [];
  return v.map((h) => {
    const o = (h ?? {}) as Record<string, unknown>;
    const j = (o.judge ?? {}) as Record<string, unknown>;
    return {
      attempt: Number(o.attempt ?? 0),
      angle: String(o.angle ?? ""),
      temperature: Number(o.temperature ?? 0),
      score: Number(o.score ?? 0),
      accepted: Boolean(o.accepted),
      judge: {
        score: Number(j.score ?? o.score ?? 0),
        reasons: String(j.reasons ?? ""),
        worst_gap: String(j.worst_gap ?? ""),
      },
      supervisor_rounds: Number(o.supervisor_rounds ?? 0),
      sub_topics: Array.isArray(o.sub_topics) ? o.sub_topics.map(String) : [],
    };
  });
}

function asTrace(v: unknown): ODRTrace {
  const o = (v ?? {}) as Record<string, unknown>;
  return {
    brief: String(o.brief ?? ""),
    sub_questions: Array.isArray(o.sub_questions) ? o.sub_questions.map(String) : [],
    supervisor_rounds: Number(o.supervisor_rounds ?? 0),
    findings: asFindings(o.findings),
    notes: asNotes(o.notes),
  };
}

// 把后端 research 槽映射成 ResearchRun。缺字段给出安全缺省。
export function adaptResearch(raw: RawResearch): ResearchRun {
  const engine = raw.engine === "legacy" ? "legacy" : "odr";
  const status =
    raw.status === "accepted" || raw.status === "best_effort" ? raw.status : "pending";
  return {
    engine,
    status,
    score: Number(raw.score ?? 0),
    attempts: Number(raw.attempts ?? 0),
    threshold: Number(raw.threshold ?? 0),
    digest: String(raw.digest ?? ""),
    sources: asSources(raw.sources),
    history: asHistory(raw.history),
    odr: asTrace(raw.odr),
  };
}

// 拉取某标的的真实研究记录。任何失败(服务未起/404/超时/解析错)都返回 null,
// 让调用方优雅回退到本地 mock。
export async function fetchResearchRun(
  target: string,
  timeoutMs = 2500,
): Promise<ResearchRun | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}/api/research/${encodeURIComponent(target)}`, {
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    const raw = (await res.json()) as RawResearch;
    if (!raw || typeof raw !== "object") return null;
    return adaptResearch(raw);
  } catch {
    return null; // 服务没起 / 网络错 / 超时 —— 回退 mock
  } finally {
    clearTimeout(timer);
  }
}

// ===== K 线 =====
// 后端 /api/kline/<target> 的原始形状(见 serve.py::_load_kline)。
interface RawKline {
  status?: string;
  symbol?: string;
  timeframe?: string;
  range?: string;
  bars?: unknown[];
  features?: unknown;
}

function asBars(v: unknown): KlineBar[] {
  if (!Array.isArray(v)) return [];
  return v.map((b) => {
    const o = (b ?? {}) as Record<string, unknown>;
    return {
      t: String(o.t ?? ""),
      o: Number(o.o ?? 0),
      h: Number(o.h ?? 0),
      l: Number(o.l ?? 0),
      c: Number(o.c ?? 0),
      v: Number(o.v ?? 0),
    };
  });
}

// features 结构较深且后端已保证 shape;这里只做「存在即透传、缺失即 null」。
function asFeatures(v: unknown): KlineFeatures | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  // trend 是必有键;若连它都没有,视为占位(无特征)。
  if (!o.trend) return null;
  return v as KlineFeatures;
}

export function adaptKline(raw: RawKline): KlineData {
  const status =
    raw.status === "ok" || raw.status === "error" ? raw.status : "placeholder";
  return {
    status,
    symbol: String(raw.symbol ?? ""),
    timeframe: String(raw.timeframe ?? ""),
    range: String(raw.range ?? ""),
    bars: asBars(raw.bars),
    features: asFeatures(raw.features),
  };
}

// 拉取某标的的真实 K 线(OHLCV + 技术特征)。失败返回 null → 调用方回退 mock。
export async function fetchKline(
  target: string,
  timeoutMs = 2500,
): Promise<KlineData | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}/api/kline/${encodeURIComponent(target)}`, {
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    const raw = (await res.json()) as RawKline;
    if (!raw || typeof raw !== "object") return null;
    const data = adaptKline(raw);
    // 后端返回但无 bars(占位/网络降级) —— 视为拿不到,让前端回退 mock。
    if (data.status !== "ok" || data.bars.length === 0) return null;
    return data;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

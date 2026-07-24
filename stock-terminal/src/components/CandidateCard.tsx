import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, TrendingUp, Info, Loader2, CheckCircle2, AlertCircle, Coins } from "lucide-react";
import type { WatchItem } from "@/types/analysis";
import { dirColor, signPct } from "@/lib/utils";
import { useAuth } from "@/store/auth";
import { startResearch } from "@/lib/auth";

// 未深度研究的候选股：只展示它真实拥有的字段（报价/评分/点评），
// 并诚实标注"尚未深度研究"。若服务端配置了大模型,用户可主动发起一次真实 ODR 研究。
export default function CandidateCard({ item }: { item: WatchItem }) {
  const { config, wallet, refreshWallet } = useAuth();
  const [state, setState] = useState<"idle" | "starting" | "queued" | "error" | "nocredit">("idle");
  const [msg, setMsg] = useState("");

  async function onStart() {
    setState("starting");
    setMsg("");
    try {
      await startResearch(item.code);
      setState("queued");
      setMsg("已加入研究队列,预计数分钟。可在稍后刷新查看结果。");
      void refreshWallet(); // 扣点后刷新余额
    } catch (err) {
      const detail = err instanceof Error ? err.message : "发起失败";
      // 后端点数不足返回 402,detail 含"充值"字样;单独区分成"去充值"引导态。
      if (detail.includes("充值") || detail.includes("余额")) {
        setState("nocredit");
      } else {
        setState("error");
      }
      setMsg(detail);
    }
  }

  const enabled = config.research_enabled;
  const cost = config.research_cost ?? 1;
  const freeLeft = wallet?.free_left ?? 0;
  const balance = wallet?.balance ?? 0;

  return (
    <motion.div
      key={item.code}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-lg border border-subtle bg-panel p-4"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xs text-ink-3">{item.code}</span>
          <h2 className="font-display text-lg font-700 text-ink">{item.name}</h2>
        </div>
        <span className="rounded-sm border border-subtle px-1.5 py-0.5 text-2xs text-ink-3">
          候选 · 未深度研究
        </span>
      </div>

      <div className="mt-2 flex items-end gap-3">
        <span className="font-mono text-3xl font-700" style={{ color: dirColor(item.changePct) }}>
          {item.price.toFixed(2)}
        </span>
        <span className="mb-1 font-mono text-sm font-600" style={{ color: dirColor(item.changePct) }}>
          {signPct(item.changePct)}
        </span>
        <span className="mb-1 font-mono text-2xs text-ink-3">{item.marketCap}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-md border border-subtle bg-inset px-3 py-2">
          <div className="flex items-center gap-1 text-2xs text-ink-3">
            <TrendingUp size={11} /> 候选池评分
          </div>
          <div className="mt-1 font-mono text-xl font-700 text-ink">{item.score}</div>
        </div>
        <div className="rounded-md border border-subtle bg-inset px-3 py-2">
          <div className="flex items-center gap-1 text-2xs text-ink-3">
            <Info size={11} /> 一句话逻辑
          </div>
          <div className="mt-1 text-xs leading-relaxed text-ink-2">{item.note}</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-md border border-dashed border-subtle bg-inset/50 px-3 py-2.5">
        <Search size={14} style={{ color: "var(--accent)" }} />
        <div className="flex-1 text-2xs leading-relaxed text-ink-3">
          {state === "queued" ? (
            <span className="flex items-center gap-1" style={{ color: "var(--accent)" }}>
              <CheckCircle2 size={12} /> {msg}
            </span>
          ) : state === "nocredit" ? (
            <span className="flex items-center gap-1" style={{ color: "var(--down)" }}>
              <Coins size={12} /> {msg}
              <Link to="/billing" className="ml-1 font-600 underline" style={{ color: "var(--accent)" }}>
                去充值
              </Link>
            </span>
          ) : state === "error" ? (
            <span className="flex items-center gap-1" style={{ color: "var(--down)" }}>
              <AlertCircle size={12} /> {msg}
            </span>
          ) : enabled ? (
            <>
              该标的尚未运行深度研究。点击可发起一次真实 ODR 研究流程(约数分钟)。
              {freeLeft > 0 ? (
                <span className="ml-1" style={{ color: "var(--accent)" }}>今日剩余免费 {freeLeft} 次。</span>
              ) : (
                <span className="ml-1">今日免费已用完,本次消耗 {cost} 点(余额 {balance} 点)。</span>
              )}
            </>
          ) : (
            <>该标的尚未运行深度研究,且服务器暂未配置大模型凭据,当前无法在线发起。</>
          )}
        </div>
        <button
          onClick={onStart}
          disabled={!enabled || state === "starting" || state === "queued"}
          className="flex shrink-0 items-center gap-1 rounded-md border px-2.5 py-1 text-2xs transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            borderColor: enabled ? "var(--accent)" : "var(--border-subtle)",
            color: enabled && (state === "idle" || state === "nocredit") ? "var(--accent)" : "var(--text-muted)",
          }}
          title={enabled ? "发起一次真实深度研究" : "服务器未配置大模型凭据"}
        >
          {state === "starting" && <Loader2 size={11} className="animate-spin" />}
          {state === "queued" ? "已入队" : "发起深度研究"}
        </button>
      </div>
    </motion.div>
  );
}

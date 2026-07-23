import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  FlaskConical,
  FileText,
  ListTree,
  Layers3,
  FileCheck2,
  Link2,
  Check,
  Zap,
  Wifi,
  WifiOff,
  Loader2,
  CandlestickChart,
} from "lucide-react";
import { researchRuns } from "@/data/research";
import { klineRuns } from "@/data/kline";
import { stocks } from "@/data/stocks";
import { useTerminal } from "@/store/terminal";
import { fetchResearchRun, fetchKline } from "@/lib/api";
import type { ResearchRun, KlineData } from "@/types/analysis";
import RetryTimeline from "./RetryTimeline";
import SubFindingCard from "./SubFindingCard";
import KlineChart from "./KlineChart";
import KlineFeaturePanel from "./KlineFeaturePanel";

function SectionHead({ icon, title, hint }: { icon: React.ReactNode; title: string; hint?: string }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="font-display text-2xs font-600 uppercase tracking-wider text-ink-3">{title}</span>
      </div>
      {hint && <span className="font-mono text-2xs text-ink-3">{hint}</span>}
    </div>
  );
}

type Source = "loading" | "live" | "offline";

// ODR 研究过程抽屉 —— 从右侧滑入,完整回放一只股票的多智能体深研过程:
// 顶栏(引擎/最终分/状态)→ 研究简报 → 子问题拆解 → 子研究卡(含反思/来源)
// → 压缩笔记 → 最终报告摘要 → 评分·重跑闭环时间线。
//
// 数据来源渐进增强:打开时先向后端 bridge (serve.py) 拉真实 context.json;
// 拉到就用真实数据(标「实时」),拉不到回退本地 mock(标「离线」)。
export default function ResearchPanel() {
  const { researchOpenId, closeResearch } = useTerminal();
  const open = researchOpenId != null;
  const stock = researchOpenId ? stocks.find((s) => s.id === researchOpenId) : undefined;
  const mock = researchOpenId ? researchRuns[researchOpenId] : undefined;
  const klineMock = researchOpenId ? klineRuns[researchOpenId] : undefined;

  const [run, setRun] = useState<ResearchRun | undefined>(undefined);
  const [source, setSource] = useState<Source>("loading");
  const [kline, setKline] = useState<KlineData | undefined>(undefined);

  useEffect(() => {
    if (!researchOpenId) return;
    let alive = true;
    setSource("loading");
    setRun(undefined);
    setKline(undefined);
    fetchResearchRun(researchOpenId).then((live) => {
      if (!alive) return;
      if (live) {
        setRun(live);
        setSource("live");
      } else {
        setRun(mock); // 后端不可达 —— 回退本地 mock
        setSource("offline");
      }
    });
    // K 线独立拉取:拉到真实 OHLCV 就画真实,否则回退离线合成序列。
    fetchKline(researchOpenId).then((live) => {
      if (!alive) return;
      setKline(live ?? klineMock);
    });
    return () => {
      alive = false;
    };
    // researchOpenId 变化即重新拉取;mock 由 id 决定,无需单列依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchOpenId]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 遮罩 */}
          <motion.div
            className="fixed inset-0 z-40 bg-black/55 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={closeResearch}
          />

          {/* 抽屉 */}
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-screen w-full max-w-[560px] flex-col border-l border-strong bg-space shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            {/* 抽屉头 */}
            <div className="flex items-center justify-between border-b border-subtle bg-panel px-4 py-3">
              <div className="flex items-center gap-2">
                <FlaskConical size={15} className="text-accent" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-display text-sm font-700 text-ink">
                      {stock?.quote.name ?? researchOpenId} · 深度研究过程
                    </span>
                    {run && (
                      <span className="rounded-sm px-1.5 py-0.5 font-mono text-2xs font-600" style={{ color: "var(--accent)", background: "var(--accent-dim)" }}>
                        {run.engine.toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="font-mono text-2xs text-ink-3">
                      Open-Deep-Research · 多智能体 supervisor + 并行子研究
                    </span>
                    {source === "live" && (
                      <span className="inline-flex items-center gap-1 rounded-sm px-1 py-0.5 font-mono text-2xs" style={{ color: "var(--accent)", background: "var(--accent-dim)" }}>
                        <Wifi size={9} />
                        实时
                      </span>
                    )}
                    {source === "offline" && (
                      <span className="inline-flex items-center gap-1 rounded-sm px-1 py-0.5 font-mono text-2xs" style={{ color: "var(--amber)", background: "rgba(240,180,60,0.14)" }}>
                        <WifiOff size={9} />
                        离线 mock
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                onClick={closeResearch}
                className="rounded-sm p-1.5 text-ink-3 transition-colors hover:bg-elevated hover:text-ink"
              >
                <X size={16} />
              </button>
            </div>

            {source === "loading" ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-2xs text-ink-3">
                <Loader2 size={20} className="animate-spin text-accent" />
                正在拉取研究记录…
              </div>
            ) : !run ? (
              <div className="flex flex-1 items-center justify-center text-2xs text-ink-3">
                暂无该标的的研究记录
              </div>
            ) : (
              <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
                {/* 最终评分状态条 */}
                <div
                  className="flex items-center justify-between rounded-md border p-3"
                  style={{ borderColor: "var(--accent)", background: "var(--accent-dim)" }}
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md font-mono text-base font-700"
                      style={{ color: "var(--accent)", background: "var(--bg-space)", boxShadow: "inset 0 0 0 1px var(--accent)" }}
                    >
                      {run.score.toFixed(1)}
                    </span>
                    <div>
                      <div className="flex items-center gap-1 font-display text-xs font-700" style={{ color: "var(--accent)" }}>
                        {run.status === "accepted" ? <Check size={13} strokeWidth={3} /> : <Zap size={13} />}
                        {run.status === "accepted" ? "已达标 · 采纳" : "尽力而为 · 取最优"}
                      </div>
                      <div className="mt-0.5 font-mono text-2xs text-ink-3">
                        阈值 {run.threshold.toFixed(1)} · 共 {run.attempts} 次 ODR 运行
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-2xs text-ink-3">judge 独立打分</div>
                    <div className="font-mono text-sm font-700" style={{ color: "var(--accent)" }}>
                      {run.score.toFixed(1)} / 10
                    </div>
                  </div>
                </div>

                {/* 技术面 · K线 */}
                {kline && (
                  <section>
                    <SectionHead
                      icon={<CandlestickChart size={12} className="text-accent" />}
                      title="技术面 · K线"
                      hint={`${kline.symbol} · ${kline.timeframe}`}
                    />
                    <div className="rounded-md border border-subtle bg-panel p-2.5">
                      <KlineChart data={kline} />
                      {kline.features && (
                        <div className="mt-2.5 border-t border-subtle pt-2.5">
                          <KlineFeaturePanel features={kline.features} />
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* 研究简报 */}
                <section>
                  <SectionHead icon={<FileText size={12} className="text-accent" />} title="研究简报 · brief" />
                  <p className="rounded-md border border-subtle bg-panel p-2.5 text-2xs leading-relaxed text-ink-2">
                    {run.odr.brief}
                  </p>
                </section>

                {/* 子问题拆解 */}
                <section>
                  <SectionHead
                    icon={<ListTree size={12} className="text-accent" />}
                    title="子问题拆解 · supervisor"
                    hint={`${run.odr.supervisor_rounds} 轮编排`}
                  />
                  <div className="flex flex-col gap-1">
                    {run.odr.sub_questions.map((q, i) => (
                      <div key={i} className="flex items-center gap-2 rounded-sm border border-subtle bg-inset px-2 py-1.5">
                        <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full font-mono text-2xs font-700" style={{ color: "var(--accent)", background: "var(--accent-dim)" }}>
                          {i + 1}
                        </span>
                        <span className="text-2xs text-ink-2">{q}</span>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 子研究发现 */}
                <section>
                  <SectionHead
                    icon={<FlaskConical size={12} className="text-accent" />}
                    title="并行子研究 · findings"
                    hint={`${run.odr.findings.length} 个子研究`}
                  />
                  <div className="flex flex-col gap-2">
                    {run.odr.findings.map((f, i) => (
                      <SubFindingCard key={i} finding={f} index={i} />
                    ))}
                  </div>
                </section>

                {/* 压缩笔记 */}
                <section>
                  <SectionHead icon={<Layers3 size={12} className="text-accent" />} title="压缩笔记 · compression" />
                  <div className="flex flex-col gap-1.5">
                    {run.odr.notes.map((n, i) => (
                      <div key={i} className="rounded-sm border border-subtle bg-inset px-2.5 py-2">
                        <div className="mb-0.5 font-display text-2xs font-600 text-ink">{n.topic}</div>
                        <p className="text-2xs leading-snug text-ink-2">{n.compressed}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 最终报告摘要 */}
                <section>
                  <SectionHead icon={<FileCheck2 size={12} className="text-accent" />} title="最终报告 · digest" />
                  <div className="rounded-md border p-3" style={{ borderColor: "var(--border-strong)", background: "var(--bg-panel)" }}>
                    <p className="text-xs leading-relaxed text-ink">{run.digest}</p>
                    {run.sources.length > 0 && (
                      <div className="mt-2.5 border-t border-subtle pt-2">
                        <div className="mb-1 font-display text-2xs font-600 uppercase tracking-wider text-ink-3">
                          引用来源
                        </div>
                        <div className="flex flex-col gap-1">
                          {run.sources.map((s, i) => (
                            <a
                              key={i}
                              href={s.url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-1.5 truncate text-2xs text-ink-3 transition-colors hover:text-accent"
                              title={s.title}
                            >
                              <Link2 size={10} className="shrink-0" />
                              <span className="truncate">{s.title}</span>
                              <span className="shrink-0 font-mono text-ink-3/70">{s.date}</span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* 评分 · 重跑闭环 */}
                <section>
                  <RetryTimeline history={run.history} threshold={run.threshold} />
                </section>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

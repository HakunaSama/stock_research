import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Progress, Skeleton, Tag } from "antd";
import {
  CheckCircleFilled,
  ExperimentOutlined,
  LinkOutlined,
  LoadingOutlined,
  RightOutlined,
  ThunderboltFilled,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { fetchResearchRun } from "@/lib/api";
import { fetchJobs, startResearch, type ResearchJob } from "@/lib/auth";
import { useAuth } from "@/store/auth";
import { useMarket } from "@/store/market";
import { activeStrategyName, useStrategies } from "@/store/strategy";
import type { ResearchRun } from "@/types/analysis";

// AI 深度研究卡 —— 状态机:
//   有研究产物 → judge 评分 + 最终报告摘要 + 引用来源,可打开完整过程抽屉;
//   任务进行中 → 实时进度态(排队/运行,自动轮询直至完成);
//   无产物     → 发起研究 CTA(免费额度/点数计费,对接后端任务队列)。
export default function ResearchCard({ code, name }: { code: string; name: string }) {
  const { runs, openResearch, refreshRuns } = useMarket();
  const { config, wallet, refreshWallet } = useAuth();
  const strategies = useStrategies();
  const run = runs[code];

  // 让 CTA 能显示「将使用哪份策略」(懒加载一次,已加载则无请求)
  useEffect(() => {
    strategies.ensureLoaded();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [detail, setDetail] = useState<ResearchRun | null>(null);
  const [job, setJob] = useState<ResearchJob | null>(null);
  const [action, setAction] = useState<"idle" | "starting" | "error" | "nocredit">("idle");
  const [msg, setMsg] = useState("");
  const [pollTick, setPollTick] = useState(0);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 有产物 → 拉真实研究摘要(digest/sources)
  useEffect(() => {
    let alive = true;
    setDetail(null);
    if (!run) return;
    fetchResearchRun(code).then((r) => {
      if (alive) setDetail(r);
    });
    return () => {
      alive = false;
    };
  }, [code, run?.run_id]);

  // 无产物 → 查询该标的的任务并轮询进行中的任务
  useEffect(() => {
    if (run) {
      setJob(null);
      return;
    }
    let alive = true;
    async function poll() {
      try {
        const jobs = await fetchJobs();
        if (!alive) return;
        const mine = jobs
          .filter((j) => j.target === code)
          .sort((a, b) => b.created_at - a.created_at)[0] ?? null;
        setJob(mine);
        if (mine && (mine.status === "pending" || mine.status === "running")) {
          pollTimer.current = setTimeout(poll, 8000);
        } else if (mine && mine.status === "done") {
          void refreshRuns(); // 产物就绪,切换到结果态
        }
      } catch {
        // 任务接口不可用(如只读 bridge)——静默降级为纯 CTA
      }
    }
    void poll();
    return () => {
      alive = false;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, run == null, pollTick]);

  async function onStart() {
    setAction("starting");
    setMsg("");
    try {
      await startResearch(code);
      setAction("idle");
      setPollTick((t) => t + 1); // 立即进入任务轮询
      void refreshWallet();
    } catch (err) {
      const detail = err instanceof Error ? err.message : "发起失败";
      setAction(detail.includes("充值") || detail.includes("余额") ? "nocredit" : "error");
      setMsg(detail);
    }
  }

  const cardTitle = (
    <span className="flex items-center gap-1.5 font-display text-xs font-semibold">
      <ExperimentOutlined style={{ color: "var(--accent)" }} />
      AI 深度研究
    </span>
  );

  // ---------- 已有研究产物 ----------
  if (run) {
    const accepted = run.status === "accepted";
    return (
      <Card
        size="small"
        title={cardTitle}
        extra={
          <Button
            size="small"
            type="primary"
            ghost
            icon={<RightOutlined style={{ fontSize: 10 }} />}
            iconPosition="end"
            onClick={() => openResearch(code)}
          >
            完整研究过程
          </Button>
        }
        style={{ borderColor: "rgba(130,71,255,0.35)" }}
        styles={{ body: { padding: 12 } }}
      >
        <div className="flex items-center gap-3">
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md font-mono text-base font-bold"
            style={{
              color: "var(--accent)",
              background: "var(--bg-inset)",
              boxShadow: "inset 0 0 0 1px rgba(130,71,255,0.4)",
            }}
          >
            {run.score.toFixed(1)}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 font-display text-xs font-semibold" style={{ color: "var(--accent)" }}>
              {accepted ? <CheckCircleFilled /> : <ThunderboltFilled />}
              {accepted ? "已达标 · 采纳" : "尽力而为 · 取最优"}
              <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
                {run.engine.toUpperCase()}
              </Tag>
            </div>
            <div className="mt-0.5 font-mono text-2xs text-ink-3">
              独立 judge {run.score.toFixed(1)}/10 · 阈值 {run.threshold.toFixed(1)} · {run.attempts} 次 ODR 运行
            </div>
          </div>
        </div>

        {detail == null ? (
          <Skeleton active paragraph={{ rows: 2 }} title={false} style={{ marginTop: 10 }} />
        ) : (
          <>
            <p className="mb-0 mt-2.5 text-xs leading-relaxed text-ink-2">{detail.digest}</p>
            {detail.sources.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {detail.sources.slice(0, 4).map((s, i) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex max-w-[200px] items-center gap-1 truncate rounded-sm bg-inset px-1.5 py-0.5 text-2xs text-ink-3 transition-colors hover:text-accent"
                    title={s.title}
                  >
                    <LinkOutlined style={{ fontSize: 9 }} />
                    <span className="truncate">{s.title}</span>
                  </a>
                ))}
              </div>
            )}
          </>
        )}
      </Card>
    );
  }

  // ---------- 任务进行中 ----------
  if (job && (job.status === "pending" || job.status === "running")) {
    return (
      <Card size="small" title={cardTitle} styles={{ body: { padding: 12 } }}>
        <div className="flex items-center gap-2.5">
          <LoadingOutlined style={{ fontSize: 16, color: "var(--accent)" }} />
          <div className="flex-1">
            <div className="font-display text-xs font-semibold text-ink">
              AI 深度研究进行中 · {name}
            </div>
            <div className="mt-0.5 text-2xs text-ink-3">
              {job.status === "pending" ? "任务排队中…" : "多智能体研究运行中…"}
              预计数分钟,完成后自动展示结论。
              {job.strategy_name && <span className="ml-1">策略:{job.strategy_name}</span>}
            </div>
          </div>
          <span className="font-mono text-2xs text-ink-3">#{job.id}</span>
        </div>
        <Progress
          percent={100}
          status="active"
          showInfo={false}
          strokeColor="var(--accent)"
          size={{ height: 4 }}
          style={{ marginTop: 10, marginBottom: 0 }}
        />
      </Card>
    );
  }

  // ---------- 发起研究 CTA ----------
  const enabled = config.research_enabled;
  const freeLeft = wallet?.free_left ?? 0;
  const cost = config.research_cost ?? 1;
  const failed = job?.status === "failed";

  return (
    <Card size="small" title={cardTitle} styles={{ body: { padding: 12 } }}>
      {(action === "error" || action === "nocredit" || failed) && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 10 }}
          message={
            action === "nocredit" ? (
              <span className="text-xs">
                {msg}
                <Link to="/billing" className="ml-2 font-semibold underline" style={{ color: "var(--accent)" }}>
                  去充值
                </Link>
              </span>
            ) : (
              <span className="text-xs">{action === "error" ? msg : `上次研究失败:${job?.error || "未知原因"},可重试。`}</span>
            )
          }
        />
      )}
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1 text-2xs leading-relaxed text-ink-3">
          {enabled ? (
            <>
              该标的尚未运行 AI 深度研究。发起后由多智能体完成拆解、并行调研与独立评分(约数分钟)。
              {freeLeft > 0 ? (
                <span className="ml-1" style={{ color: "var(--accent)" }}>今日剩余免费 {freeLeft} 次</span>
              ) : (
                <span className="ml-1">本次消耗 {cost} 点(余额 {wallet?.balance ?? 0} 点)</span>
              )}
              <span className="mt-0.5 block">
                将按策略
                <span className="mx-0.5 font-semibold text-ink-2">《{activeStrategyName(strategies)}》</span>
                逐条核对
                <button
                  className="ml-1.5 cursor-pointer border-0 bg-transparent p-0 text-2xs underline"
                  style={{ color: "var(--accent)" }}
                  onClick={strategies.openDrawer}
                >
                  更换策略
                </button>
              </span>
            </>
          ) : (
            <>该标的尚未运行 AI 深度研究;服务器暂未配置大模型凭据,当前无法在线发起。</>
          )}
        </div>
        <Button
          type="primary"
          disabled={!enabled}
          loading={action === "starting"}
          icon={<ExperimentOutlined />}
          onClick={onStart}
        >
          {failed ? "重新研究" : "发起深度研究"}
        </Button>
      </div>
    </Card>
  );
}

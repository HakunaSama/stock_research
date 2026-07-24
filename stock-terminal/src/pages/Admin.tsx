import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Coins,
  FileText,
  Loader2,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import type { AdminStats, AdminUser, LedgerEntry, Order } from "@/lib/auth";
import {
  adminAdjustCredits,
  adminFetchLedger,
  adminFetchOrders,
  adminFetchStats,
  adminFetchUsers,
} from "@/lib/auth";
import { fmtCents, fmtTs } from "@/lib/utils";

type Tab = "overview" | "users" | "orders" | "ledger";

const REASON_LABEL: Record<string, string> = {
  topup: "充值到账",
  research_spend: "研究扣点",
  refund: "失败退点",
  admin_adjust: "管理员调整",
  signup_bonus: "注册赠点",
};

// 概览统计卡
function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-subtle bg-panel p-4">
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="mt-1 font-mono text-2xl font-700 text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-2xs text-ink-3">{sub}</div>}
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  async function reload() {
    setLoading(true);
    setErr("");
    try {
      const [s, u, o, l] = await Promise.all([
        adminFetchStats(),
        adminFetchUsers(),
        adminFetchOrders(),
        adminFetchLedger(),
      ]);
      setStats(s);
      setUsers(u);
      setOrders(o);
      setLedger(l);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  // 手动充值/扣减:弹窗输入 delta。
  async function onAdjust(u: AdminUser) {
    const raw = window.prompt(
      `为用户「${u.username}」调整点数(正数充值 / 负数扣减),当前余额 ${u.balance}:`,
      "",
    );
    if (raw === null) return;
    const delta = parseInt(raw.trim(), 10);
    if (!Number.isFinite(delta) || delta === 0) {
      window.alert("请输入非零整数");
      return;
    }
    const memo = window.prompt("备注(可选):", "") ?? "";
    try {
      await adminAdjustCredits(u.id, delta, memo);
      await reload();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "调整失败");
    }
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "概览", icon: <TrendingUp size={13} /> },
    { key: "users", label: "用户", icon: <Users size={13} /> },
    { key: "orders", label: "订单", icon: <FileText size={13} /> },
    { key: "ledger", label: "流水", icon: <Coins size={13} /> },
  ];

  return (
    <div className="relative z-10 mx-auto h-screen max-w-6xl overflow-y-auto p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} style={{ color: "var(--accent)" }} />
          <h1 className="font-display text-xl font-700 text-ink">后台管理</h1>
        </div>
        <Link to="/" className="flex items-center gap-1.5 text-xs text-ink-3 hover:text-ink">
          <ArrowLeft size={14} /> 返回终端
        </Link>
      </div>

      {/* Tab 切换 */}
      <div className="mb-4 flex gap-1 rounded-md border border-subtle bg-inset p-0.5">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-sm py-1.5 text-xs font-600 transition-colors"
            style={{
              background: tab === t.key ? "var(--bg-elevated)" : "transparent",
              color: tab === t.key ? "var(--text-primary)" : "var(--text-muted)",
            }}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {err && (
        <div
          className="mb-4 rounded-md border px-3 py-2 text-xs"
          style={{ borderColor: "var(--down)", color: "var(--down)" }}
        >
          {err}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={22} className="animate-spin" style={{ color: "var(--accent)" }} />
        </div>
      ) : (
        <>
          {/* 概览 */}
          {tab === "overview" && stats && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="总用户" value={String(stats.total_users)} />
              <StatCard label="累计研究" value={String(stats.total_jobs)} sub={`今日 ${stats.jobs_today} · 运行中 ${stats.jobs_running}`} />
              <StatCard label="已支付订单" value={String(stats.paid_orders)} />
              <StatCard label="累计营收" value={fmtCents(stats.revenue_cents)} sub={`今日 ${fmtCents(stats.revenue_today_cents)}`} />
              <StatCard label="未消耗点数(负债)" value={String(stats.credits_outstanding)} sub="用户已购未用点数" />
            </div>
          )}

          {/* 用户 */}
          {tab === "users" && (
            <div className="overflow-hidden rounded-lg border border-subtle bg-panel">
              <table className="w-full text-xs">
                <thead className="text-ink-3">
                  <tr className="border-b border-subtle">
                    <th className="px-3 py-2 text-left font-500">ID</th>
                    <th className="px-3 py-2 text-left font-500">用户名</th>
                    <th className="px-3 py-2 text-right font-500">余额</th>
                    <th className="px-3 py-2 text-right font-500">累计充值</th>
                    <th className="px-3 py-2 text-right font-500">累计消耗</th>
                    <th className="px-3 py-2 text-center font-500">角色</th>
                    <th className="px-3 py-2 text-right font-500">操作</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-ink-2">
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-subtle/50 last:border-0">
                      <td className="px-3 py-2">{u.id}</td>
                      <td className="px-3 py-2 font-sans">{u.username}</td>
                      <td className="px-3 py-2 text-right font-600 text-ink">{u.balance}</td>
                      <td className="px-3 py-2 text-right">{u.total_topup}</td>
                      <td className="px-3 py-2 text-right">{u.total_spent}</td>
                      <td className="px-3 py-2 text-center font-sans">
                        {u.is_admin ? (
                          <span style={{ color: "var(--accent)" }}>管理员</span>
                        ) : (
                          <span className="text-ink-3">普通</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => void onAdjust(u)}
                          className="rounded-sm border border-subtle px-2 py-0.5 font-sans text-2xs text-ink-2 transition-colors hover:border-strong hover:text-ink"
                        >
                          充值/扣减
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 订单 */}
          {tab === "orders" && (
            <div className="overflow-hidden rounded-lg border border-subtle bg-panel">
              {orders.length === 0 ? (
                <div className="px-3 py-8 text-center text-2xs text-ink-3">暂无订单</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="text-ink-3">
                    <tr className="border-b border-subtle">
                      <th className="px-3 py-2 text-left font-500">订单号</th>
                      <th className="px-3 py-2 text-right font-500">用户</th>
                      <th className="px-3 py-2 text-left font-500">套餐</th>
                      <th className="px-3 py-2 text-right font-500">点数</th>
                      <th className="px-3 py-2 text-right font-500">金额</th>
                      <th className="px-3 py-2 text-center font-500">状态</th>
                      <th className="px-3 py-2 text-right font-500">时间</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-ink-2">
                    {orders.map((o) => (
                      <tr key={o.id} className="border-b border-subtle/50 last:border-0">
                        <td className="px-3 py-2 text-2xs">{o.out_trade_no}</td>
                        <td className="px-3 py-2 text-right">#{o.user_id}</td>
                        <td className="px-3 py-2 font-sans">{o.plan_code}</td>
                        <td className="px-3 py-2 text-right">{o.credits}</td>
                        <td className="px-3 py-2 text-right">{fmtCents(o.amount_cents)}</td>
                        <td className="px-3 py-2 text-center font-sans">
                          {o.status === "paid" ? (
                            <span style={{ color: "var(--up)" }}>已支付</span>
                          ) : (
                            <span className="text-ink-3">{o.status}</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right text-2xs text-ink-3">{fmtTs(o.paid_at ?? o.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* 流水 */}
          {tab === "ledger" && (
            <div className="overflow-hidden rounded-lg border border-subtle bg-panel">
              {ledger.length === 0 ? (
                <div className="px-3 py-8 text-center text-2xs text-ink-3">暂无流水</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="text-ink-3">
                    <tr className="border-b border-subtle">
                      <th className="px-3 py-2 text-right font-500">用户</th>
                      <th className="px-3 py-2 text-left font-500">类型</th>
                      <th className="px-3 py-2 text-right font-500">变动</th>
                      <th className="px-3 py-2 text-right font-500">余额</th>
                      <th className="px-3 py-2 text-left font-500">备注</th>
                      <th className="px-3 py-2 text-right font-500">时间</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-ink-2">
                    {ledger.map((l) => (
                      <tr key={l.id} className="border-b border-subtle/50 last:border-0">
                        <td className="px-3 py-2 text-right">#{l.user_id}</td>
                        <td className="px-3 py-2 font-sans">{REASON_LABEL[l.reason] ?? l.reason}</td>
                        <td
                          className="px-3 py-2 text-right font-600"
                          style={{ color: l.amount >= 0 ? "var(--up)" : "var(--down)" }}
                        >
                          {l.amount >= 0 ? "+" : ""}
                          {l.amount}
                        </td>
                        <td className="px-3 py-2 text-right">{l.balance_after}</td>
                        <td className="px-3 py-2 font-sans text-2xs text-ink-3">{l.memo || "-"}</td>
                        <td className="px-3 py-2 text-right text-2xs text-ink-3">{fmtTs(l.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

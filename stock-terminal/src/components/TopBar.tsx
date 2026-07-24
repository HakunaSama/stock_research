import { Activity, Coins, LogOut, RefreshCw, Shield, TrendingUp, User, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { marketSummary as m } from "@/data/stocks";
import { dirColor, signPct, fmtMoney } from "@/lib/utils";
import { useAuth } from "@/store/auth";

export default function TopBar() {
  const { user, wallet, logout } = useAuth();
  return (
    <header className="relative z-10 flex items-center justify-between border-b border-subtle bg-panel/80 px-5 py-2.5 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-dim">
          <Activity size={16} strokeWidth={2.4} style={{ color: "var(--accent)" }} />
        </div>
        <div>
          <div className="font-display text-[15px] font-700 tracking-wide text-ink">
            量化决策终端
          </div>
          <div className="text-2xs uppercase tracking-[0.25em] text-ink-3">
            STOCK RESEARCH AGENT
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-3">{m.index}</span>
          <span className="font-mono text-[15px] font-600 text-ink">
            {m.indexValue.toFixed(2)}
          </span>
          <span
            className="font-mono text-xs font-600"
            style={{ color: dirColor(m.indexChangePct) }}
          >
            {signPct(m.indexChangePct)}
          </span>
        </div>

        <div className="h-6 w-px bg-subtle" />

        <div className="flex items-center gap-2">
          <Wallet size={14} className="text-ink-3" />
          <span className="text-xs text-ink-3">持仓 {m.positionCount} 只 · 浮盈</span>
          <span
            className="font-mono text-[15px] font-600"
            style={{ color: dirColor(m.totalPnl) }}
          >
            {m.totalPnl > 0 ? "+" : ""}
            {fmtMoney(m.totalPnl)}
          </span>
          <span
            className="font-mono text-xs font-600"
            style={{ color: dirColor(m.totalPnlPct) }}
          >
            {signPct(m.totalPnlPct)}
          </span>
        </div>

        <div className="h-6 w-px bg-subtle" />

        <div className="flex items-center gap-2 text-ink-2">
          <TrendingUp size={14} style={{ color: "var(--up)" }} />
          <span className="font-mono text-xs">{m.time}</span>
          <button className="ml-1 flex items-center gap-1 rounded-sm border border-subtle bg-elevated px-2 py-1 text-2xs text-ink-2 transition-colors hover:border-strong hover:text-ink">
            <RefreshCw size={11} />
            刷新
          </button>
        </div>

        {user && (
          <>
            <div className="h-6 w-px bg-subtle" />
            {/* 点数余额 + 充值入口 */}
            <Link
              to="/billing"
              className="flex items-center gap-1.5 rounded-sm border border-subtle bg-elevated px-2 py-1 transition-colors hover:border-strong"
              title="点数余额 · 点击充值"
            >
              <Coins size={13} style={{ color: "var(--accent)" }} />
              <span className="font-mono text-xs font-600 text-ink">{wallet?.balance ?? 0}</span>
              <span className="text-2xs text-ink-3">点</span>
              {wallet && wallet.free_left > 0 && (
                <span className="ml-0.5 text-2xs text-ink-3">· 今日免费 {wallet.free_left}</span>
              )}
            </Link>

            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-xs text-ink-2">
                <User size={13} className="text-ink-3" />
                {user.username}
                {user.is_admin && (
                  <span
                    className="ml-0.5 rounded-sm px-1 text-2xs font-600"
                    style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
                  >
                    管理员
                  </span>
                )}
              </span>
              {user.is_admin && (
                <Link
                  to="/admin"
                  className="flex items-center gap-1 rounded-sm border border-subtle bg-elevated px-2 py-1 text-2xs text-ink-2 transition-colors hover:border-strong hover:text-ink"
                  title="后台管理"
                >
                  <Shield size={11} />
                  后台
                </Link>
              )}
              <button
                onClick={() => void logout()}
                className="flex items-center gap-1 rounded-sm border border-subtle bg-elevated px-2 py-1 text-2xs text-ink-2 transition-colors hover:border-strong hover:text-ink"
                title="退出登录"
              >
                <LogOut size={11} />
                退出
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}

import { useState } from "react";
import { Avatar, Button, Dropdown, Tag, Tooltip } from "antd";
import {
  CrownOutlined,
  LogoutOutlined,
  SafetyOutlined,
  SlidersOutlined,
  StockOutlined,
  UserOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { dirColor, signPct } from "@/lib/utils";
import { useAuth } from "@/store/auth";
import { useMarket } from "@/store/market";
import { useStrategies } from "@/store/strategy";
import AccountModal from "./AccountModal";
import SearchBox from "./SearchBox";
import StrategyDrawer from "./StrategyDrawer";

// 顶栏 —— 品牌 / 实时大盘指数 / 全局搜索 / 策略库 / 钱包与账户(antd Dropdown 菜单)。
export default function TopBar() {
  const { user, wallet, logout } = useAuth();
  const indices = useMarket((s) => s.indices);
  const lastUpdated = useMarket((s) => s.lastUpdated);
  const openStrategies = useStrategies((s) => s.openDrawer);
  const navigate = useNavigate();
  const [accountOpen, setAccountOpen] = useState(false);

  const menuItems = [
    {
      key: "strategies",
      icon: <SlidersOutlined />,
      label: "策略库（热插拔）",
      onClick: openStrategies,
    },
    {
      key: "account",
      icon: <SafetyOutlined />,
      label: "账号与安全",
      onClick: () => setAccountOpen(true),
    },
    {
      key: "billing",
      icon: <WalletOutlined />,
      label: "钱包与充值",
      onClick: () => navigate("/billing"),
    },
    ...(user?.is_admin
      ? [{
          key: "admin",
          icon: <CrownOutlined />,
          label: "后台管理",
          onClick: () => navigate("/admin"),
        }]
      : []),
    { type: "divider" as const },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      danger: true,
      onClick: () => void logout(),
    },
  ];

  return (
    <header className="relative z-30 flex items-center justify-between gap-4 border-b border-subtle bg-panel/85 px-4 py-2 backdrop-blur-md">
      {/* 品牌 */}
      <div className="flex shrink-0 items-center gap-2.5">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{ background: "var(--accent-dim)", boxShadow: "inset 0 0 0 1px rgba(130,71,255,0.35)" }}
        >
          <StockOutlined style={{ fontSize: 16, color: "var(--accent)" }} />
        </div>
        <div>
          <div className="font-display text-[14px] font-bold tracking-wide text-ink">
            AI 投研终端
          </div>
          <div className="text-2xs uppercase tracking-[0.22em] text-ink-3">
            Stock Research Terminal
          </div>
        </div>
      </div>

      {/* 实时指数条 */}
      <div className="flex min-w-0 flex-1 items-center gap-5 overflow-hidden pl-2">
        {indices.slice(0, 4).map((ix) => (
          <div key={ix.symbol} className="flex shrink-0 items-baseline gap-1.5">
            <span className="text-2xs text-ink-3">{ix.name}</span>
            <span className="font-mono text-[13px] font-semibold" style={{ color: dirColor(ix.change_pct) }}>
              {ix.price.toFixed(2)}
            </span>
            <span className="font-mono text-2xs font-medium" style={{ color: dirColor(ix.change_pct) }}>
              {signPct(ix.change_pct)}
            </span>
          </div>
        ))}
        {indices.length === 0 && (
          <div className="flex items-center gap-2">
            <span className="skeleton h-3.5 w-32" />
            <span className="skeleton h-3.5 w-32" />
          </div>
        )}
        {lastUpdated != null && (
          <span className="flex shrink-0 items-center gap-1.5 font-mono text-2xs text-ink-3">
            <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full" style={{ background: "var(--down)" }} />
            {new Date(lastUpdated).toLocaleTimeString("zh-CN", { hour12: false })}
          </span>
        )}
      </div>

      {/* 搜索 + 账户 */}
      <div className="flex shrink-0 items-center gap-3">
        <SearchBox />

        {user && (
          <>
            <Tooltip title="点数余额 · 点击充值">
              <Link to="/billing">
                <Button size="middle">
                  <WalletOutlined style={{ color: "var(--accent)" }} />
                  <span className="font-mono font-semibold">{wallet?.balance ?? 0}</span>
                  <span className="text-2xs text-ink-3">点</span>
                  {wallet && wallet.free_left > 0 && (
                    <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
                      免费 {wallet.free_left}
                    </Tag>
                  )}
                  {wallet?.sub_active && (
                    <Tag color="gold" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
                      会员
                    </Tag>
                  )}
                </Button>
              </Link>
            </Tooltip>

            <Dropdown menu={{ items: menuItems }} placement="bottomRight" trigger={["click"]}>
              <button className="flex items-center gap-1.5 rounded-md px-1 py-0.5 transition-colors hover:bg-elevated">
                <Avatar size={26} icon={<UserOutlined />} style={{ background: "var(--accent-dim)", color: "var(--accent)" }} />
                <span className="text-xs text-ink-2">{user.username}</span>
                {user.is_admin && (
                  <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
                    管理员
                  </Tag>
                )}
              </button>
            </Dropdown>
          </>
        )}
      </div>

      <StrategyDrawer />
      <AccountModal open={accountOpen} onClose={() => setAccountOpen(false)} />
    </header>
  );
}

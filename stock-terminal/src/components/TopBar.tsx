import { useEffect, useState } from "react";
import { Avatar, Button, Dropdown, Tag, Tooltip } from "antd";
import {
  BgColorsOutlined,
  CheckOutlined,
  CrownOutlined,
  LogoutOutlined,
  SafetyOutlined,
  SlidersOutlined,
  UserOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { dirColor, signPct } from "@/lib/utils";
import { useAuth } from "@/store/auth";
import { useMarket } from "@/store/market";
import { activeStrategyName, useStrategies } from "@/store/strategy";
import { useSkin } from "@/theme/SkinContext";
import AccountModal from "./AccountModal";
import BrandMark from "./BrandMark";
import SearchBox from "./SearchBox";
import StrategyDrawer from "./StrategyDrawer";

// 顶栏 —— 品牌 / 实时大盘指数 / 独立策略中心 / 全局搜索 / 钱包与账户。
export default function TopBar() {
  const { user, wallet, logout } = useAuth();
  const indices = useMarket((s) => s.indices);
  const lastUpdated = useMarket((s) => s.lastUpdated);
  const openStrategies = useStrategies((s) => s.openDrawer);
  const ensureStrategiesLoaded = useStrategies((s) => s.ensureLoaded);
  const strategyName = useStrategies(activeStrategyName);
  const navigate = useNavigate();
  const [accountOpen, setAccountOpen] = useState(false);
  const { skinId, setSkin, skins } = useSkin();

  useEffect(() => {
    ensureStrategiesLoaded();
  }, [ensureStrategiesLoaded]);

  const menuItems = [
    {
      key: "account",
      icon: <SafetyOutlined />,
      label: "个人中心",
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

  const skinMenuItems = skins.map((skin) => ({
    key: skin.id,
    icon: skin.id === skinId ? <CheckOutlined /> : <span className="inline-block w-3" />,
    label: skin.label,
    onClick: () => setSkin(skin.id),
  }));

  return (
    <header className="app-topbar">
      {/* 品牌 */}
      <Link to="/" className="topbar-brand flex shrink-0 items-center no-underline">
        <BrandMark size="sm" />
      </Link>

      {/* 实时指数条 */}
      <div className="topbar-ticker flex min-w-0 items-center gap-5 overflow-hidden pl-2">
        {indices.slice(0, 4).map((ix) => (
          <div key={ix.symbol} className="topbar-index-item flex shrink-0 items-baseline gap-1.5">
            <span className="topbar-index-name text-2xs text-ink-3">{ix.name}</span>
            <span className="topbar-index-price font-mono text-[13px] font-semibold" style={{ color: dirColor(ix.change_pct) }}>
              {ix.price.toFixed(2)}
            </span>
            <span className="topbar-index-change font-mono text-2xs font-medium" style={{ color: dirColor(ix.change_pct) }}>
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
          <span data-testid="market-last-updated" className="topbar-index-time flex shrink-0 items-center gap-1.5 font-mono text-2xs text-ink-3">
            <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full" style={{ background: "var(--down)" }} />
            {new Date(lastUpdated).toLocaleTimeString("zh-CN", { hour12: false })}
          </span>
        )}
      </div>

      {/* 策略中心：从账户菜单提升为独立、持续可见的一级入口 */}
      <nav
        aria-label="策略中心"
        className="topbar-strategy flex shrink-0 items-center rounded-md border border-subtle bg-panel-2 p-0.5 shadow-sm"
      >
        <Link
          to="/hall"
          className="flex h-8 items-center gap-1.5 rounded-[7px] px-3 text-xs font-semibold text-ink-2 no-underline transition-colors hover:bg-elevated hover:text-ink"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          策略大厅
        </Link>
        <span className="h-4 w-px bg-subtle" aria-hidden="true" />
        <Tooltip title={`当前使用：${strategyName}`}>
          <button
            type="button"
            className="flex h-8 items-center gap-1.5 whitespace-nowrap rounded-[7px] border-0 bg-transparent px-3 text-xs font-semibold text-ink-2 transition-colors hover:bg-elevated hover:text-ink"
            onClick={openStrategies}
          >
            <SlidersOutlined style={{ color: "var(--accent)" }} />
            <span>我的策略</span>
          </button>
        </Tooltip>
      </nav>

      {/* 搜索 + 账户 */}
      <div className="topbar-actions flex shrink-0 items-center gap-3">
        <SearchBox />

        <Dropdown menu={{ items: skinMenuItems }} placement="bottomRight" trigger={["click"]}>
          <Tooltip title="切换界面皮肤">
            <Button aria-label="切换界面皮肤" icon={<BgColorsOutlined />}>
              <span className="topbar-skin-label">皮肤</span>
            </Button>
          </Tooltip>
        </Dropdown>

        {user && (
          <>
            <Tooltip title="点数余额 · 点击充值">
              <Link to="/billing">
                <Button size="middle">
                  <WalletOutlined style={{ color: "var(--accent)" }} />
                  <span className="topbar-wallet-meta font-mono font-semibold">{wallet?.balance ?? 0}</span>
                  <span className="topbar-wallet-meta text-2xs text-ink-3">点</span>
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
                <Avatar
                  size={26}
                  src={user.avatar_url || undefined}
                  icon={!user.avatar_url ? <UserOutlined /> : undefined}
                  style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
                />
                <span className="topbar-user-name text-xs text-ink-2">{user.display_name || user.username}</span>
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

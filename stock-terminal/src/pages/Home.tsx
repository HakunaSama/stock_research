import { useEffect, useState } from "react";
import { BarChart3, CandlestickChart, ShieldCheck } from "lucide-react";
import TopBar from "@/components/TopBar";
import StockDetail from "@/components/StockDetail";
import SidePanel from "@/components/SidePanel";
import Discipline from "@/components/Discipline";
import ResearchPanel from "@/components/ResearchPanel";
import ResizableSplit from "@/components/layout/ResizableSplit";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { startMarketPolling } from "@/store/market";

// 主终端 —— 竞品式三段布局:
//   顶栏(品牌/实时指数/全局搜索/账户)
//   左侧股票池(自选 + 全市场榜单) + 主区个股详情(报价/AI研究/K线/资讯)
//   右侧滑入的 ODR 研究过程抽屉
// 行情每 5s 轮询真实数据源,页面隐藏时自动暂停。
export default function Home() {
  useEffect(() => startMarketPolling(), []);
  const isMobile = useMediaQuery("(max-width: 819px)");
  const [mobileView, setMobileView] = useState<"market" | "detail" | "rules">("detail");

  const marketPanel = <SidePanel />;
  const disciplinePanel = <div className="h-full overflow-y-auto"><Discipline /></div>;
  const detailPanel = <main className="h-full overflow-y-auto overscroll-contain pr-1"><StockDetail /></main>;

  return (
    <div className="app-shell relative z-10 flex min-h-0 flex-col overflow-hidden">
      <TopBar />

      {isMobile ? (
        <div className="mobile-workspace min-h-0 flex-1 overflow-hidden">
          <section hidden={mobileView !== "market"} className="h-full min-h-0 p-2">{marketPanel}</section>
          <section hidden={mobileView !== "detail"} className="h-full min-h-0 overflow-hidden p-2">{detailPanel}</section>
          <section hidden={mobileView !== "rules"} className="h-full min-h-0 overflow-y-auto p-2">{disciplinePanel}</section>
        </div>
      ) : (
        <div className="min-h-0 flex-1 p-3">
          <ResizableSplit
            direction="horizontal"
            initialSize={300}
            minFirst={240}
            minSecond={520}
            storageKey="cheese:layout:sidebar-width"
            firstLabel="行情侧栏"
            secondLabel="个股工作区"
            first={
              <ResizableSplit
                direction="vertical"
                initialSize={560}
                minFirst={260}
                minSecond={116}
                storageKey="cheese:layout:market-height"
                firstLabel="股票池"
                secondLabel="执行纪律"
                first={marketPanel}
                second={disciplinePanel}
              />
            }
            second={detailPanel}
          />
        </div>
      )}

      {isMobile && (
        <nav className="mobile-workspace-nav" aria-label="移动端工作区">
          {([
            ["market", BarChart3, "行情"],
            ["detail", CandlestickChart, "个股"],
            ["rules", ShieldCheck, "纪律"],
          ] as const).map(([key, Icon, label]) => (
            <button key={key} type="button" className={mobileView === key ? "is-active" : ""} onClick={() => setMobileView(key)}>
              <Icon size={17} /><span>{label}</span>
            </button>
          ))}
        </nav>
      )}

      <ResearchPanel />
    </div>
  );
}

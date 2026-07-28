import { useEffect } from "react";
import TopBar from "@/components/TopBar";
import StockDetail from "@/components/StockDetail";
import SidePanel from "@/components/SidePanel";
import Discipline from "@/components/Discipline";
import ResearchPanel from "@/components/ResearchPanel";
import { startMarketPolling } from "@/store/market";

// 主终端 —— 竞品式三段布局:
//   顶栏(品牌/实时指数/全局搜索/账户)
//   左侧股票池(自选 + 全市场榜单) + 主区个股详情(报价/AI研究/K线/资讯)
//   右侧滑入的 ODR 研究过程抽屉
// 行情每 5s 轮询真实数据源,页面隐藏时自动暂停。
export default function Home() {
  useEffect(() => startMarketPolling(), []);

  return (
    <div className="relative z-10 flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex flex-1 gap-3 overflow-hidden p-3">
        <aside className="flex w-[300px] shrink-0 flex-col gap-3 overflow-hidden">
          <div className="min-h-0 flex-1">
            <SidePanel />
          </div>
          <Discipline />
        </aside>

        <main className="flex-1 overflow-y-auto pr-1">
          <StockDetail />
        </main>
      </div>

      <ResearchPanel />
    </div>
  );
}

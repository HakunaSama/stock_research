import TopBar from "@/components/TopBar";
import StockCard from "@/components/StockCard";
import CandidateCard from "@/components/CandidateCard";
import Watchlist from "@/components/Watchlist";
import Discipline from "@/components/Discipline";
import ResearchPanel from "@/components/ResearchPanel";
import { stocks } from "@/data/stocks";
import { watchlist } from "@/data/watchlist";
import { useTerminal, researchedIds } from "@/store/terminal";

export default function Home() {
  const selectedId = useTerminal((s) => s.selectedId);
  // 选中的是"未深度研究"的候选股时，主区顶部显示一张精简候选卡。
  const candidate =
    selectedId && !researchedIds.has(selectedId)
      ? watchlist.find((w) => w.code === selectedId)
      : undefined;

  return (
    <div className="relative z-10 flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex flex-1 gap-3 overflow-hidden p-3">
        {/* 主区：选中未研究候选股时置顶精简卡 + 双列个股分析卡 */}
        <main className="flex-1 overflow-y-auto pr-1">
          {candidate && (
            <div className="mb-3">
              <CandidateCard item={candidate} />
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {stocks.map((s, i) => (
              <StockCard key={s.id} data={s} index={i} />
            ))}
          </div>
        </main>

        {/* 右固定侧栏 */}
        <aside className="flex w-[300px] shrink-0 flex-col gap-3 overflow-hidden">
          <div className="min-h-0 flex-1">
            <Watchlist />
          </div>
          <Discipline />
        </aside>
      </div>

      {/* ODR 深度研究过程抽屉（从右滑入，接 zustand researchOpenId） */}
      <ResearchPanel />
    </div>
  );
}

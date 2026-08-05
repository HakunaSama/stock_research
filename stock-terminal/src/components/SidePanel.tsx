import { useEffect, useMemo, useState } from "react";
import { Button, Empty, Segmented, Skeleton, Tabs, Tooltip } from "antd";
import {
  CheckOutlined,
  CloseOutlined,
  PlusOutlined,
  ThunderboltFilled,
} from "@ant-design/icons";
import { fetchRank } from "@/lib/market";
import { dirColor, fmtAmountCn, signPct } from "@/lib/utils";
import { useMarket, type WatchSort } from "@/store/market";
import type { RankItem, RankKind } from "@/types/market";

// 侧栏股票池 —— 自选(用户管理,本地持久化) + 全市场实时榜单(涨幅/跌幅/成交额)。
// 榜单来自东财全市场列表,每 10s 刷新;内容区独立滚动,任意榜单股点击即看。

const RANK_TABS: { key: RankKind; label: string }[] = [
  { key: "pct_desc", label: "涨幅榜" },
  { key: "pct_asc", label: "跌幅榜" },
  { key: "amount", label: "成交额" },
];

function Row({
  code,
  name,
  price,
  pct,
  sub,
  index,
  researched,
  active,
  inWatchlist,
  onPick,
  onAdd,
  onRemove,
}: {
  code: string;
  name: string;
  price: number | null;
  pct: number | null;
  sub?: string;
  index?: number;
  researched: boolean;
  active: boolean;
  inWatchlist: boolean;
  onPick: () => void;
  onAdd?: () => void;
  onRemove?: () => void;
}) {
  return (
    <div
      className="group relative flex cursor-pointer items-center gap-2 border-b border-subtle/60 py-1.5 pl-3 pr-2 transition-colors hover:bg-elevated/60"
      style={{ background: active ? "var(--bg-elevated)" : undefined }}
      onClick={onPick}
    >
      <span
        className="absolute left-0 top-0 h-full w-0.5"
        style={{ background: active ? "var(--accent)" : "transparent" }}
      />
      {index != null && (
        <span
          className="w-4 shrink-0 text-center font-mono text-2xs"
          style={{ color: index < 3 ? "var(--accent)" : "var(--text-muted)" }}
        >
          {index + 1}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium text-ink">{name}</span>
          {researched && (
            <Tooltip title="已完成 AI 深度研究">
              <ThunderboltFilled style={{ fontSize: 10, color: "var(--accent)" }} />
            </Tooltip>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-1.5 font-mono text-2xs text-ink-3">
          <span>{code}</span>
          {sub && <span>{sub}</span>}
        </div>
      </div>
      <div className="shrink-0 text-right">
        {price != null && pct != null ? (
          <>
            <div className="font-mono text-xs font-semibold" style={{ color: dirColor(pct) }}>
              {price.toFixed(2)}
            </div>
            <div className="font-mono text-2xs" style={{ color: dirColor(pct) }}>
              {signPct(pct)}
            </div>
          </>
        ) : price == null && pct == null && sub === undefined ? (
          <Skeleton.Node active style={{ width: 44, height: 26 }} />
        ) : (
          <span className="font-mono text-2xs text-ink-3">停牌</span>
        )}
      </div>
      {/* 悬停操作:榜单加自选 / 自选移除 */}
      {onAdd && (
        <Tooltip title={inWatchlist ? "已在自选" : "加入自选"}>
          <Button
            size="small"
            type="text"
            icon={inWatchlist ? <CheckOutlined style={{ fontSize: 10 }} /> : <PlusOutlined style={{ fontSize: 10 }} />}
            className="opacity-0 transition-opacity group-hover:opacity-100"
            style={{ color: inWatchlist ? "var(--down)" : "var(--accent)" }}
            disabled={inWatchlist}
            onClick={(e) => {
              e.stopPropagation();
              onAdd();
            }}
          />
        </Tooltip>
      )}
      {onRemove && (
        <Tooltip title="移出自选">
          <Button
            size="small"
            type="text"
            icon={<CloseOutlined style={{ fontSize: 10 }} />}
            className="opacity-0 transition-opacity group-hover:opacity-100"
            style={{ color: "var(--text-muted)" }}
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
          />
        </Tooltip>
      )}
    </div>
  );
}

function WatchTab() {
  const { watchlist, quotes, runs, selectedCode, select, removeStock, sort, setSort } =
    useMarket();

  const rows = useMemo(() => {
    const list = watchlist.map((w) => ({ ...w, quote: quotes[w.code] }));
    if (sort === "pctDesc")
      return [...list].sort(
        (a, b) => (b.quote?.change_pct ?? -Infinity) - (a.quote?.change_pct ?? -Infinity),
      );
    if (sort === "pctAsc")
      return [...list].sort(
        (a, b) => (a.quote?.change_pct ?? Infinity) - (b.quote?.change_pct ?? Infinity),
      );
    return list;
  }, [watchlist, quotes, sort]);

  return (
    <div className="flex h-full flex-col">
      <div className="px-2 pb-1.5">
        <Segmented
          block
          size="small"
          value={sort}
          onChange={(v) => setSort(v as WatchSort)}
          options={[
            { label: "自选序", value: "default" },
            { label: "涨幅", value: "pctDesc" },
            { label: "跌幅", value: "pctAsc" },
          ]}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span className="text-2xs text-ink-3">
                自选池为空,用顶部搜索或榜单「+」添加
              </span>
            }
            className="mt-6"
          />
        ) : (
          rows.map((w) => (
            <Row
              key={w.code}
              code={w.code}
              name={w.quote?.name ?? w.name}
              price={w.quote?.price ?? null}
              pct={w.quote?.change_pct ?? null}
              sub={w.quote?.total_market_cap != null ? fmtAmountCn(w.quote.total_market_cap) : undefined}
              researched={w.code in runs}
              active={selectedCode === w.code}
              inWatchlist
              onPick={() => select(w.code)}
              onRemove={() => removeStock(w.code)}
              onAdd={undefined}
            />
          ))
        )}
      </div>
    </div>
  );
}

function RankTab({ kind }: { kind: RankKind }) {
  const { watchlist, runs, selectedCode, select, addStock } = useMarket();
  const [rows, setRows] = useState<RankItem[] | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      const list = await fetchRank(kind, 30);
      if (!alive) return;
      setRows((prev) => (list.length > 0 ? list : prev ?? []));
      timer = setTimeout(load, 10000);
    }
    void load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [kind]);

  if (rows == null) {
    return (
      <div className="flex flex-col gap-2 px-3 pt-2">
        {[...Array(8)].map((_, i) => (
          <Skeleton.Node key={i} active style={{ width: "100%", height: 34 }} />
        ))}
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={<span className="text-2xs text-ink-3">榜单暂不可用</span>}
        className="mt-6"
      />
    );
  }
  return (
    <div data-testid={`rank-scroll-${kind}`} className="h-full min-h-0 overflow-y-auto overscroll-contain">
      {rows.map((r, i) => (
        <Row
          key={r.code}
          code={r.code}
          name={r.name}
          price={r.price}
          pct={r.change_pct}
          sub={kind === "amount" && r.amount != null ? fmtAmountCn(r.amount) : undefined}
          index={i}
          researched={r.code in runs}
          active={selectedCode === r.code}
          inWatchlist={watchlist.some((w) => w.code === r.code)}
          onPick={() => select(r.code)}
          onAdd={() => addStock({ code: r.code, name: r.name })}
        />
      ))}
    </div>
  );
}

export default function SidePanel() {
  const count = useMarket((s) => s.watchlist.length);
  return (
    <div className="card flex h-full flex-col overflow-hidden">
      <Tabs
        size="small"
        className="side-tabs flex h-full flex-col"
        tabBarStyle={{ padding: "0 10px", marginBottom: 8 }}
        items={[
          {
            key: "watch",
            label: `自选 ${count}`,
            children: <WatchTab />,
          },
          ...RANK_TABS.map((t) => ({
            key: t.key,
            label: t.label,
            children: <RankTab kind={t.key} />,
          })),
        ]}
      />
    </div>
  );
}

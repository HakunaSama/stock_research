import { useEffect, useRef, useState } from "react";
import { AutoComplete, Input } from "antd";
import type { InputRef } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { searchStocks } from "@/lib/market";
import { useMarket } from "@/store/market";
import type { SearchHit } from "@/types/market";

const MARKET_LABEL: Record<string, string> = { sh: "沪", sz: "深", bj: "京" };

// 全局股票搜索(antd AutoComplete) —— 代码/名称/拼音首字母,
// 选中即加入自选并切换主视图;快捷键 “/” 聚焦。
export default function SearchBox() {
  const { watchlist, addStock } = useMarket();
  const [kw, setKw] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<InputRef>(null);

  useEffect(() => {
    const q = kw.trim();
    if (!q) {
      setHits([]);
      setBusy(false);
      return;
    }
    setBusy(true);
    const timer = setTimeout(async () => {
      const res = await searchStocks(q);
      setHits(res);
      setBusy(false);
    }, 220);
    return () => clearTimeout(timer);
  }, [kw]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && !(e.target instanceof HTMLInputElement)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const options = hits.map((h) => {
    const inList = watchlist.some((w) => w.code === h.code);
    return {
      value: h.code,
      label: (
        <div className="flex items-center gap-2">
          <span className="w-14 shrink-0 font-mono text-2xs text-ink-3">{h.code}</span>
          <span className="flex-1 truncate text-xs text-ink">{h.name}</span>
          <span className="shrink-0 rounded-sm bg-inset px-1 font-mono text-2xs text-ink-3">
            {MARKET_LABEL[h.market] ?? h.market}
          </span>
          <span className="shrink-0 text-2xs" style={{ color: inList ? "var(--text-muted)" : "var(--accent)" }}>
            {inList ? "已自选" : "+ 自选"}
          </span>
        </div>
      ),
    };
  });

  return (
    <AutoComplete
      className="topbar-search"
      value={kw}
      options={options}
      onChange={setKw}
      onSelect={(code: string) => {
        const hit = hits.find((h) => h.code === code);
        if (hit) addStock({ code: hit.code, name: hit.name });
        setKw("");
        setHits([]);
        inputRef.current?.blur();
      }}
      popupMatchSelectWidth={300}
      notFoundContent={
        kw.trim() ? (
          <span className="text-2xs text-ink-3">{busy ? "搜索中…" : "未找到匹配的 A 股标的"}</span>
        ) : null
      }
    >
      <Input
        ref={inputRef}
        size="middle"
        prefix={<SearchOutlined style={{ color: "var(--text-muted)" }} />}
        suffix={<span className="rounded-sm border border-subtle px-1 font-mono text-2xs text-ink-3">/</span>}
        placeholder="搜索代码 / 名称 / 拼音"
        allowClear
      />
    </AutoComplete>
  );
}

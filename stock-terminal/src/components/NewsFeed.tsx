import { useEffect, useState } from "react";
import { Card, Empty, Skeleton, Typography } from "antd";
import { ReadOutlined } from "@ant-design/icons";
import { fetchNews } from "@/lib/market";
import type { NewsArticle } from "@/types/market";

// 个股实时资讯 —— 东方财富公开接口的真实新闻,按时间倒序。
export default function NewsFeed({ code }: { code: string }) {
  const [items, setItems] = useState<NewsArticle[] | null>(null);

  useEffect(() => {
    let alive = true;
    setItems(null);
    fetchNews(code).then((list) => {
      if (alive) setItems(list);
    });
    return () => {
      alive = false;
    };
  }, [code]);

  return (
    <Card
      size="small"
      title={
        <span className="flex items-center gap-1.5 font-display text-xs font-semibold">
          <ReadOutlined style={{ color: "var(--accent)" }} />
          个股资讯
        </span>
      }
      extra={<span className="font-mono text-2xs text-ink-3">东方财富 · 实时</span>}
      styles={{ body: { padding: "4px 12px" } }}
    >
      {items == null ? (
        <Skeleton active paragraph={{ rows: 4 }} title={false} style={{ padding: "8px 0" }} />
      ) : items.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span className="text-2xs text-ink-3">暂无相关资讯</span>}
        />
      ) : (
        <ul className="m-0 list-none divide-y divide-subtle p-0">
          {items.map((n) => (
            <li key={`${n.date}-${n.url}-${n.title}`} className="flex py-2">
              <div className="min-w-0 flex-1">
                <Typography.Link
                  href={n.url || undefined}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "var(--text-secondary)", fontSize: 12 }}
                >
                  {n.title}
                </Typography.Link>
                <div className="mt-0.5 flex items-center gap-2 font-mono text-2xs text-ink-3">
                  <span>{n.date}</span>
                  {n.source && <span>{n.source}</span>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

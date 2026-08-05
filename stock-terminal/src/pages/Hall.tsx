import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  App,
  Button,
  Drawer,
  Empty,
  Input,
  Segmented,
  Spin,
  Tag,
  Typography,
} from "antd";
import {
  ArrowLeftOutlined,
  CommentOutlined,
  HeartFilled,
  HeartOutlined,
  StarFilled,
  StarOutlined,
  SlidersOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  adoptHallStrategy,
  deleteHallComment,
  fetchHallComments,
  fetchHallStrategies,
  fetchHallTags,
  fetchMyFavorites,
  postHallComment,
  toggleHallFavorite,
  toggleHallLike,
  type HallComment,
  type HallSort,
  type HallStrategy,
} from "@/lib/strategy";
import { useStrategies } from "@/store/strategy";
import { fmtTs } from "@/lib/utils";
import StrategyDrawer from "@/components/StrategyDrawer";

type Tab = "hall" | "favorites";

export default function Hall() {
  const { message } = App.useApp();
  const refreshMine = useStrategies((s) => s.refresh);
  const openStrategies = useStrategies((s) => s.openDrawer);

  const [tab, setTab] = useState<Tab>("hall");
  const [sort, setSort] = useState<HallSort>("hot");
  const [tag, setTag] = useState("");
  const [q, setQ] = useState("");
  const [qDraft, setQDraft] = useState("");
  const [tags, setTags] = useState<{ tag: string; count: number }[]>([]);
  const [items, setItems] = useState<HallStrategy[]>([]);
  const [loading, setLoading] = useState(true);

  const [detail, setDetail] = useState<HallStrategy | null>(null);
  const [comments, setComments] = useState<HallComment[]>([]);
  const [commentDraft, setCommentDraft] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadList() {
    setLoading(true);
    try {
      if (tab === "favorites") {
        const res = await fetchMyFavorites();
        setItems(res.items);
      } else {
        const res = await fetchHallStrategies({ tag, q, sort, limit: 50 });
        setItems(res.items);
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchHallTags()
      .then((r) => setTags(r.tags))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, sort, tag, q]);

  function patchItem(id: number, patch: Partial<HallStrategy>) {
    setItems((prev) => prev.map((x) => (x.id === id ? { ...x, ...patch } : x)));
    setDetail((d) => (d && d.id === id ? { ...d, ...patch } : d));
  }

  async function onLike(s: HallStrategy) {
    try {
      const res = await toggleHallLike(s.id);
      patchItem(s.id, { liked: res.liked, like_count: res.like_count });
    } catch (e) {
      message.error(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function onFavorite(s: HallStrategy) {
    try {
      const res = await toggleHallFavorite(s.id);
      patchItem(s.id, { favorited: res.favorited, favorite_count: res.favorite_count });
      if (tab === "favorites" && !res.favorited) {
        setItems((prev) => prev.filter((x) => x.id !== s.id));
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function openDetail(s: HallStrategy) {
    setDetail(s);
    setCommentDraft("");
    try {
      const res = await fetchHallComments(s.id);
      setComments(res.comments);
    } catch {
      setComments([]);
    }
  }

  async function onComment() {
    if (!detail) return;
    const body = commentDraft.trim();
    if (!body) return;
    setBusy(true);
    try {
      await postHallComment(detail.id, body);
      const res = await fetchHallComments(detail.id);
      setComments(res.comments);
      patchItem(detail.id, { comment_count: (detail.comment_count || 0) + 1 });
      setCommentDraft("");
      message.success("评论已发布");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "评论失败");
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteComment(cid: number) {
    try {
      await deleteHallComment(cid);
      setComments((prev) => prev.filter((c) => c.id !== cid));
      if (detail) patchItem(detail.id, { comment_count: Math.max(0, detail.comment_count - 1) });
    } catch (e) {
      message.error(e instanceof Error ? e.message : "删除失败");
    }
  }

  async function onAdopt(s: HallStrategy, activate: boolean) {
    setBusy(true);
    try {
      await adoptHallStrategy(s.id, activate);
      await refreshMine();
      message.success(activate ? "已采用并激活，可立即用于研究" : "已复制到我的策略库");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "采用失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="responsive-page relative z-10 mx-auto h-dvh max-w-5xl overflow-y-auto p-3 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link to="/" className="flex items-center gap-1 text-xs text-ink-3 hover:text-ink">
            <ArrowLeftOutlined /> 返回终端
          </Link>
          <h1 className="m-0 font-display text-xl font-700 text-ink">策略大厅</h1>
        </div>
        <div className="flex items-center gap-2">
          <Segmented
            value={tab}
            onChange={(v) => setTab(v as Tab)}
            options={[
              { label: "发现", value: "hall" },
              { label: "我的收藏", value: "favorites" },
            ]}
          />
          <Button icon={<SlidersOutlined />} onClick={openStrategies}>
            我的策略
          </Button>
        </div>
      </div>

      {tab === "hall" && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Input.Search
              allowClear
              placeholder="搜索策略名 / 内容 / 作者"
              value={qDraft}
              onChange={(e) => setQDraft(e.target.value)}
              onSearch={(v) => setQ(v.trim())}
              style={{ width: 260 }}
            />
            <Segmented
              size="small"
              value={sort}
              onChange={(v) => setSort(v as HallSort)}
              options={[
                { label: "热门", value: "hot" },
                { label: "最新", value: "new" },
                { label: "点赞", value: "likes" },
                { label: "评论", value: "comments" },
              ]}
            />
          </div>

          {tags.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-1.5">
              <Tag
                color={!tag ? "purple" : undefined}
                className="cursor-pointer"
                onClick={() => setTag("")}
              >
                全部
              </Tag>
              {tags.map((t) => (
                <Tag
                  key={t.tag}
                  color={tag === t.tag ? "purple" : undefined}
                  className="cursor-pointer"
                  onClick={() => setTag(tag === t.tag ? "" : t.tag)}
                >
                  #{t.tag}
                  <span className="ml-1 opacity-60">{t.count}</span>
                </Tag>
              ))}
            </div>
          )}
        </>
      )}

      {loading ? (
        <div className="flex justify-center py-20">
          <Spin />
        </div>
      ) : items.length === 0 ? (
        <Empty
          description={
            <span className="text-xs text-ink-3">
              {tab === "favorites"
                ? "还没有收藏，去大厅逛逛吧"
                : "大厅还没有公开策略。打开「我的策略」，创建策略后即可发布到大厅。"}
            </span>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((s) => (
            <article
              key={s.id}
              className="card cursor-pointer px-4 py-3.5 transition-shadow hover:shadow-md"
              onClick={() => void openDetail(s)}
            >
              <div className="flex items-start gap-2">
                <h2 className="m-0 flex-1 font-display text-sm font-700 text-ink">{s.name}</h2>
                {s.is_owner && (
                  <Tag color="blue" style={{ marginInlineEnd: 0, fontSize: 10 }}>我的</Tag>
                )}
              </div>
              <div className="mt-1 text-2xs text-ink-3">
                @{s.author_name}
                {s.published_at ? ` · ${fmtTs(s.published_at)}` : ""}
              </div>
              {s.tags?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {s.tags.map((t) => (
                    <Tag
                      key={t}
                      className="cursor-pointer"
                      style={{ marginInlineEnd: 0, fontSize: 10 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setTab("hall");
                        setTag(t);
                      }}
                    >
                      #{t}
                    </Tag>
                  ))}
                </div>
              )}
              <Typography.Paragraph
                className="!mb-0 !mt-2 text-xs leading-relaxed text-ink-2"
                ellipsis={{ rows: 3 }}
              >
                {s.summary || s.raw_text}
              </Typography.Paragraph>
              <div
                className="mt-3 flex items-center gap-3 text-xs text-ink-3"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  className="inline-flex items-center gap-1 border-0 bg-transparent p-0"
                  style={{ color: s.liked ? "var(--accent)" : undefined, cursor: "pointer" }}
                  onClick={() => void onLike(s)}
                >
                  {s.liked ? <HeartFilled /> : <HeartOutlined />} {s.like_count}
                </button>
                <button
                  className="inline-flex items-center gap-1 border-0 bg-transparent p-0"
                  style={{ color: s.favorited ? "var(--favorite)" : undefined, cursor: "pointer" }}
                  onClick={() => void onFavorite(s)}
                >
                  {s.favorited ? <StarFilled /> : <StarOutlined />} {s.favorite_count}
                </button>
                <span className="inline-flex items-center gap-1">
                  <CommentOutlined /> {s.comment_count}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}

      <Drawer
        title={detail?.name || "策略详情"}
        size="min(560px, 100vw)"
        open={!!detail}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <>
            <div className="mb-2 text-2xs text-ink-3">
              @{detail.author_name}
              {detail.published_at ? ` · 发布于 ${fmtTs(detail.published_at)}` : ""}
            </div>
            {detail.tags?.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1">
                {detail.tags.map((t) => (
                  <Tag key={t} style={{ marginInlineEnd: 0 }}>#{t}</Tag>
                ))}
              </div>
            )}
            {detail.summary && (
              <p className="mt-0 text-xs font-600 text-ink-2">{detail.summary}</p>
            )}
            <Typography.Paragraph className="whitespace-pre-wrap text-xs leading-relaxed text-ink-2">
              {detail.raw_text}
            </Typography.Paragraph>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Button
                icon={detail.liked ? <HeartFilled /> : <HeartOutlined />}
                onClick={() => void onLike(detail)}
              >
                {detail.like_count}
              </Button>
              <Button
                icon={detail.favorited ? <StarFilled /> : <StarOutlined />}
                onClick={() => void onFavorite(detail)}
              >
                {detail.favorited ? "已收藏" : "收藏"} ({detail.favorite_count})
              </Button>
              {!detail.is_owner && (
                <>
                  <Button loading={busy} onClick={() => void onAdopt(detail, false)}>
                    采用到我的库
                  </Button>
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    loading={busy}
                    onClick={() => void onAdopt(detail, true)}
                  >
                    采用并激活
                  </Button>
                </>
              )}
            </div>

            <div className="mb-2 font-display text-xs font-700 text-ink">
              评论 ({comments.length})
            </div>
            <div className="mb-3 flex gap-2">
              <Input.TextArea
                rows={2}
                maxLength={500}
                placeholder="说点什么…"
                value={commentDraft}
                onChange={(e) => setCommentDraft(e.target.value)}
              />
              <Button type="primary" loading={busy} onClick={() => void onComment()}>
                发送
              </Button>
            </div>
            <div className="space-y-2">
              {comments.map((c) => (
                <div key={c.id} className="rounded-md border border-subtle bg-panel px-3 py-2">
                  <div className="flex items-center gap-2 text-2xs text-ink-3">
                    <span className="font-600 text-ink-2">@{c.username}</span>
                    <span>{fmtTs(c.created_at)}</span>
                    {c.is_mine && (
                      <button
                        className="ml-auto border-0 bg-transparent p-0 text-2xs"
                        style={{ color: "var(--down)", cursor: "pointer" }}
                        onClick={() => void onDeleteComment(c.id)}
                      >
                        删除
                      </button>
                    )}
                  </div>
                  <div className="mt-1 whitespace-pre-wrap text-xs text-ink-2">{c.body}</div>
                </div>
              ))}
              {comments.length === 0 && (
                <div className="py-4 text-center text-2xs text-ink-3">还没有评论，来抢沙发</div>
              )}
            </div>
          </>
        )}
      </Drawer>
      <StrategyDrawer />
    </div>
  );
}

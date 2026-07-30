import { useState } from "react";
import { Link } from "react-router-dom";
import { App, Button, Drawer, Empty, Input, Popconfirm, Switch, Tag, Typography } from "antd";
import {
  CheckOutlined,
  DeleteOutlined,
  EditOutlined,
  GlobalOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useStrategies } from "@/store/strategy";
import type { Strategy } from "@/lib/strategy";

// 策略库抽屉 —— 个人策略热插拔管理:
//   新建/编辑/删除 + 标签 + 发布到策略大厅;激活其一供研究管线使用。

interface FormState {
  id: number | null;
  name: string;
  text: string;
  summary: string;
  tagsText: string; // 空格或逗号分隔,也可用 #标签
}

const EMPTY_FORM: FormState = { id: null, name: "", text: "", summary: "", tagsText: "" };

function parseTags(input: string): string[] {
  return input
    .split(/[\s,，、#]+/)
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 8);
}

export default function StrategyDrawer() {
  const {
    drawerOpen, closeDrawer, loaded, activeId, builtin, strategies,
    create, update, remove, activate, publish,
  } = useStrategies();
  const { message } = App.useApp();

  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function onSave(alsoActivate: boolean) {
    if (!form) return;
    const name = form.name.trim();
    const text = form.text.trim();
    if (!name) return void message.warning("请给策略起个名字");
    if (text.length < 10) return void message.warning("策略描述太短，至少 10 个字");
    setSaving(true);
    try {
      const tags = parseTags(form.tagsText);
      const summary = form.summary.trim();
      if (form.id == null) {
        await create({ name, rawText: text, summary, tags, activate: alsoActivate });
        message.success(alsoActivate ? "策略已保存并激活" : "策略已保存");
      } else {
        await update({ id: form.id, name, rawText: text, summary, tags });
        if (alsoActivate) await activate(form.id);
        message.success("策略已更新");
      }
      setForm(null);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function onActivate(id: number) {
    setBusyId(id);
    try {
      await activate(id);
      message.success(id === 0 ? "已切回内置示例策略" : "策略已激活，之后的研究将按它执行");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(id: number) {
    try {
      await remove(id);
      message.success("策略已删除");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function onTogglePublish(s: Strategy, next: boolean) {
    setBusyId(s.id);
    try {
      await publish(s.id, next, s.summary, s.tags);
      message.success(next ? "已发布到策略大厅" : "已从大厅撤回");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  function StrategyRow({ s }: { s: Strategy }) {
    const isActive = s.id === activeId;
    return (
      <div
        className="card mb-2.5 px-3.5 py-3"
        style={isActive ? { borderColor: "rgba(130,71,255,0.45)" } : undefined}
      >
        <div className="flex items-center gap-2">
          <span className="font-display text-[13px] font-semibold text-ink">{s.name}</span>
          {isActive && (
            <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
              使用中
            </Tag>
          )}
          {s.is_public && (
            <Tag color="blue" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
              大厅公开
            </Tag>
          )}
          <span className="ml-auto font-mono text-2xs text-ink-3">
            {new Date(s.updated_at * 1000).toLocaleDateString("zh-CN")}
          </span>
        </div>
        {s.tags?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {s.tags.map((t) => (
              <Tag key={t} style={{ marginInlineEnd: 0, fontSize: 10 }}>#{t}</Tag>
            ))}
          </div>
        )}
        <Typography.Paragraph
          className="!mb-0 !mt-1.5 text-xs leading-relaxed text-ink-2"
          ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
        >
          {s.raw_text}
        </Typography.Paragraph>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {!isActive && (
            <Button
              size="small"
              type="primary"
              ghost
              icon={<ThunderboltOutlined />}
              loading={busyId === s.id}
              onClick={() => void onActivate(s.id)}
            >
              使用此策略
            </Button>
          )}
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() =>
              setForm({
                id: s.id,
                name: s.name,
                text: s.raw_text,
                summary: s.summary || "",
                tagsText: (s.tags || []).map((t) => `#${t}`).join(" "),
              })
            }
          >
            编辑
          </Button>
          <Popconfirm
            title="删除该策略？"
            description={isActive ? "它正在使用中，删除后将回退到内置示例。" : "删除后不可恢复。"}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => void onDelete(s.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
          <span className="ml-auto flex items-center gap-1.5 text-2xs text-ink-3">
            <GlobalOutlined />
            发布大厅
            <Switch
              size="small"
              checked={s.is_public}
              loading={busyId === s.id}
              onChange={(v) => void onTogglePublish(s, v)}
            />
          </span>
        </div>
      </div>
    );
  }

  return (
    <Drawer
      title={<span className="font-display text-sm font-semibold">策略库 · 热插拔</span>}
      width={520}
      open={drawerOpen}
      onClose={() => {
        setForm(null);
        closeDrawer();
      }}
      extra={
        <Link to="/hall" onClick={closeDrawer} className="text-xs" style={{ color: "var(--accent)" }}>
          去策略大厅 →
        </Link>
      }
    >
      <p className="mb-3 mt-0 text-2xs leading-relaxed text-ink-3">
        用自然语言描述交易策略。可加 #标签，并一键发布到策略大厅供其他人点赞、收藏与评论。
        发起 AI 深度研究时，系统会按当前激活策略逐条核对。
      </p>

      {form ? (
        <div className="card mb-3 px-3.5 py-3" style={{ borderColor: "rgba(130,71,255,0.35)" }}>
          <div className="mb-2 font-display text-xs font-semibold text-ink">
            {form.id == null ? "新建策略" : "编辑策略"}
          </div>
          <Input
            placeholder="策略名称（如：均线回踩动量策略）"
            maxLength={40}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={{ marginBottom: 8 }}
          />
          <Input
            placeholder="一句话摘要（发布到大厅时展示，可选）"
            maxLength={120}
            value={form.summary}
            onChange={(e) => setForm({ ...form, summary: e.target.value })}
            style={{ marginBottom: 8 }}
          />
          <Input
            placeholder="标签：#动量 #均线 或 动量 均线（最多 8 个）"
            maxLength={80}
            value={form.tagsText}
            onChange={(e) => setForm({ ...form, tagsText: e.target.value })}
            style={{ marginBottom: 8 }}
          />
          <Input.TextArea
            placeholder={
              "示例：牛市或震荡市里，个股回踩20日均线不破、MACD金叉、成交量较5日均量放大超过50%时买入；跌破10日线或MACD死叉卖出；单笔止损-8%，单一仓位不超过30%。也可在正文里写 #动量"
            }
            rows={6}
            maxLength={4000}
            showCount
            value={form.text}
            onChange={(e) => setForm({ ...form, text: e.target.value })}
          />
          <div className="mt-3 flex items-center gap-2">
            <Button type="primary" loading={saving} icon={<CheckOutlined />} onClick={() => void onSave(true)}>
              保存并激活
            </Button>
            <Button loading={saving} onClick={() => void onSave(false)}>
              仅保存
            </Button>
            <Button type="text" onClick={() => setForm(null)}>
              取消
            </Button>
          </div>
        </div>
      ) : (
        <Button
          type="primary"
          icon={<PlusOutlined />}
          style={{ marginBottom: 12 }}
          onClick={() => setForm(EMPTY_FORM)}
        >
          新建策略
        </Button>
      )}

      {loaded && strategies.length === 0 && !form && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span className="text-2xs text-ink-3">还没有自定义策略，新建一条即可热插拔</span>}
          style={{ margin: "20px 0" }}
        />
      )}
      {strategies.map((s) => (
        <StrategyRow key={s.id} s={s} />
      ))}

      {builtin && (
        <div
          className="mb-2.5 rounded-lg border border-dashed px-3.5 py-3"
          style={{ borderColor: activeId === 0 ? "rgba(130,71,255,0.45)" : "var(--border-strong)" }}
        >
          <div className="flex items-center gap-2">
            <span className="font-display text-[13px] font-semibold text-ink">{builtin.name}</span>
            <Tag style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>内置</Tag>
            {activeId === 0 && (
              <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: "16px" }}>
                使用中
              </Tag>
            )}
          </div>
          <Typography.Paragraph
            className="!mb-0 !mt-1.5 text-xs leading-relaxed text-ink-2"
            ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
          >
            {builtin.raw_text}
          </Typography.Paragraph>
          {activeId !== 0 && (
            <div className="mt-2">
              <Button
                size="small"
                icon={<ThunderboltOutlined />}
                loading={busyId === 0}
                onClick={() => void onActivate(0)}
              >
                切回内置示例
              </Button>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

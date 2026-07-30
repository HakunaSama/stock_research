import { useState } from "react";
import { App, Button, Drawer, Empty, Input, Popconfirm, Tag, Typography } from "antd";
import {
  CheckOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useStrategies } from "@/store/strategy";
import type { Strategy } from "@/lib/strategy";

// 策略库抽屉 —— 策略热插拔的管理入口:
//   新建/编辑/删除自然语言策略,单选激活;发起研究时后端按激活策略编译执行。
//   id=0 的内置示例不可编辑删除,是未设置自定义策略时的回退。

interface FormState {
  id: number | null; // null = 新建
  name: string;
  text: string;
}

const EMPTY_FORM: FormState = { id: null, name: "", text: "" };

export default function StrategyDrawer() {
  const {
    drawerOpen, closeDrawer, loaded, activeId, builtin, strategies,
    create, update, remove, activate,
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
      if (form.id == null) {
        await create(name, text, alsoActivate);
        message.success(alsoActivate ? "策略已保存并激活" : "策略已保存");
      } else {
        await update(form.id, name, text);
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
          <span className="ml-auto font-mono text-2xs text-ink-3">
            {new Date(s.updated_at * 1000).toLocaleDateString("zh-CN")}
          </span>
        </div>
        <Typography.Paragraph
          className="!mb-0 !mt-1.5 text-xs leading-relaxed text-ink-2"
          ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
        >
          {s.raw_text}
        </Typography.Paragraph>
        <div className="mt-2 flex items-center gap-2">
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
            onClick={() => setForm({ id: s.id, name: s.name, text: s.raw_text })}
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
        </div>
      </div>
    );
  }

  return (
    <Drawer
      title={
        <span className="font-display text-sm font-semibold">
          策略库 · 热插拔
        </span>
      }
      width={520}
      open={drawerOpen}
      onClose={() => {
        setForm(null);
        closeDrawer();
      }}
    >
      <p className="mb-3 mt-0 text-2xs leading-relaxed text-ink-3">
        用自然语言描述你的交易策略（买入/卖出条件、止损与仓位规则）。发起 AI
        深度研究时，系统会把当前激活的策略编译成结构化规则，并在研究中逐条核对。
      </p>

      {/* 新建 / 编辑表单 */}
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
          <Input.TextArea
            placeholder={
              "示例：牛市或震荡市里，个股回踩20日均线不破、MACD金叉、成交量较5日均量放大超过50%时买入；跌破10日线或MACD死叉卖出；单笔止损-8%，单一仓位不超过30%。"
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

      {/* 我的策略 */}
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

      {/* 内置示例（回退策略） */}
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

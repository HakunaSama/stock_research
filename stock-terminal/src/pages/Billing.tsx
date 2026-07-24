import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Check,
  Coins,
  Loader2,
  Sparkles,
  Wallet as WalletIcon,
} from "lucide-react";
import type { LedgerEntry, Order, Plan } from "@/lib/auth";
import {
  createOrder,
  fetchLedger,
  fetchOrders,
  fetchPlans,
  simulatePayment,
} from "@/lib/auth";
import { fmtCents, fmtTs } from "@/lib/utils";
import { useAuth } from "@/store/auth";

// 流水原因 → 中文标签。
const REASON_LABEL: Record<string, string> = {
  topup: "充值到账",
  research_spend: "深度研究扣点",
  refund: "研究失败退点",
  admin_adjust: "管理员调整",
  signup_bonus: "注册赠点",
};

export default function Billing() {
  const { wallet, refreshWallet } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [provider, setProvider] = useState("stub");
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [buying, setBuying] = useState<string | null>(null); // 正在购买的套餐 code
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function reload() {
    const [, l, o] = await Promise.all([refreshWallet(), fetchLedger(), fetchOrders()]);
    setLedger(l);
    setOrders(o);
  }

  useEffect(() => {
    void (async () => {
      try {
        const p = await fetchPlans();
        setPlans(p.plans);
        setProvider(p.provider);
      } catch {
        /* ignore */
      }
      await reload();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onBuy(plan: Plan) {
    setBuying(plan.code);
    setMsg("");
    setErr("");
    try {
      const intent = await createOrder(plan.code);
      // 占位支付渠道:auto_confirm → 直接调 simulate 完成支付。
      // 真实渠道会返回 pay_url / qr_url,这里应跳转或展示二维码,再轮询订单状态。
      if (intent.auto_confirm) {
        const res = await simulatePayment(intent.out_trade_no);
        if (res.ok) {
          setMsg(`支付成功,到账 ${intent.credits} 点,当前余额 ${res.balance} 点。`);
        } else {
          setMsg(`该订单已处理,当前余额 ${res.balance} 点。`);
        }
        await reload();
      } else {
        setErr("该支付渠道需跳转支付,占位环境暂未实现真实跳转。");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "下单失败");
    } finally {
      setBuying(null);
    }
  }

  return (
    <div className="relative z-10 mx-auto h-screen max-w-5xl overflow-y-auto p-5">
      <div className="mb-5 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-1.5 text-xs text-ink-3 hover:text-ink">
          <ArrowLeft size={14} /> 返回终端
        </Link>
        <div className="flex items-center gap-2 rounded-md border border-subtle bg-panel px-3 py-1.5">
          <Coins size={15} style={{ color: "var(--accent)" }} />
          <span className="font-mono text-lg font-700 text-ink">{wallet?.balance ?? 0}</span>
          <span className="text-2xs text-ink-3">点可用</span>
          {wallet && (
            <span className="ml-1 text-2xs text-ink-3">· 今日免费 {wallet.free_left}/{wallet.daily_quota}</span>
          )}
        </div>
      </div>

      <h1 className="font-display text-xl font-700 text-ink">点数充值</h1>
      <p className="mt-1 text-xs text-ink-3">
        每次深度研究消耗 {wallet?.research_cost ?? 1} 点。每日有 {wallet?.daily_quota ?? 0} 次免费额度,用完后从点数余额扣除。
      </p>

      {(msg || err) && (
        <div
          className="mt-3 rounded-md border px-3 py-2 text-xs"
          style={{
            borderColor: err ? "var(--down)" : "var(--accent)",
            color: err ? "var(--down)" : "var(--accent)",
          }}
        >
          {err || msg}
        </div>
      )}

      {/* 套餐卡 */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => {
          const monthly = plan.kind === "monthly";
          return (
            <motion.div
              key={plan.code}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col rounded-lg border bg-panel p-4"
              style={{ borderColor: monthly ? "var(--accent)" : "var(--border-subtle)" }}
            >
              <div className="flex items-center gap-1.5">
                {monthly ? (
                  <Sparkles size={14} style={{ color: "var(--accent)" }} />
                ) : (
                  <Coins size={14} className="text-ink-3" />
                )}
                <span className="font-display text-sm font-700 text-ink">{plan.name}</span>
              </div>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="font-mono text-2xl font-700 text-ink">{plan.credits}</span>
                <span className="text-2xs text-ink-3">点{monthly ? " / 月" : ""}</span>
              </div>
              <div className="mt-1 text-2xs text-ink-3">{plan.desc}</div>
              <div className="mt-3 font-mono text-lg font-700" style={{ color: "var(--accent)" }}>
                {fmtCents(plan.amount_cents)}
              </div>
              <button
                onClick={() => void onBuy(plan)}
                disabled={buying !== null}
                className="mt-3 flex items-center justify-center gap-1.5 rounded-md py-2 text-xs font-600 text-black transition-opacity disabled:opacity-60"
                style={{ background: "var(--accent)" }}
              >
                {buying === plan.code ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <WalletIcon size={13} />
                )}
                {monthly ? "订阅" : "购买"}
              </button>
            </motion.div>
          );
        })}
      </div>

      {provider === "stub" && (
        <p className="mt-3 text-2xs text-ink-3">
          当前为占位支付渠道(stub):点击购买后自动模拟支付成功。接入真实渠道(如虎皮椒 / 支付宝当面付)后,将跳转扫码支付并通过异步回调到账。
        </p>
      )}

      {/* 订单 + 流水 */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-xs font-600 text-ink-2">最近订单</h2>
          <div className="overflow-hidden rounded-lg border border-subtle bg-panel">
            {orders.length === 0 ? (
              <div className="px-3 py-6 text-center text-2xs text-ink-3">暂无订单</div>
            ) : (
              <table className="w-full text-2xs">
                <thead className="text-ink-3">
                  <tr className="border-b border-subtle">
                    <th className="px-3 py-2 text-left font-500">套餐</th>
                    <th className="px-3 py-2 text-right font-500">点数</th>
                    <th className="px-3 py-2 text-right font-500">金额</th>
                    <th className="px-3 py-2 text-right font-500">状态</th>
                    <th className="px-3 py-2 text-right font-500">时间</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-ink-2">
                  {orders.map((o) => (
                    <tr key={o.id} className="border-b border-subtle/50 last:border-0">
                      <td className="px-3 py-2 font-sans">{o.plan_code}</td>
                      <td className="px-3 py-2 text-right">{o.credits}</td>
                      <td className="px-3 py-2 text-right">{fmtCents(o.amount_cents)}</td>
                      <td className="px-3 py-2 text-right">
                        {o.status === "paid" ? (
                          <span className="inline-flex items-center gap-0.5" style={{ color: "var(--up)" }}>
                            <Check size={10} /> 已支付
                          </span>
                        ) : (
                          <span className="text-ink-3">{o.status}</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right text-ink-3">{fmtTs(o.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-xs font-600 text-ink-2">点数流水</h2>
          <div className="overflow-hidden rounded-lg border border-subtle bg-panel">
            {ledger.length === 0 ? (
              <div className="px-3 py-6 text-center text-2xs text-ink-3">暂无流水</div>
            ) : (
              <table className="w-full text-2xs">
                <thead className="text-ink-3">
                  <tr className="border-b border-subtle">
                    <th className="px-3 py-2 text-left font-500">类型</th>
                    <th className="px-3 py-2 text-right font-500">变动</th>
                    <th className="px-3 py-2 text-right font-500">余额</th>
                    <th className="px-3 py-2 text-right font-500">时间</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-ink-2">
                  {ledger.map((l) => (
                    <tr key={l.id} className="border-b border-subtle/50 last:border-0">
                      <td className="px-3 py-2 font-sans">{REASON_LABEL[l.reason] ?? l.reason}</td>
                      <td
                        className="px-3 py-2 text-right font-600"
                        style={{ color: l.amount >= 0 ? "var(--up)" : "var(--down)" }}
                      >
                        {l.amount >= 0 ? "+" : ""}
                        {l.amount}
                      </td>
                      <td className="px-3 py-2 text-right">{l.balance_after}</td>
                      <td className="px-3 py-2 text-right text-ink-3">{fmtTs(l.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

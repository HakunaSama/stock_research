import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, Loader2, LogIn, UserPlus } from "lucide-react";
import { useAuth } from "@/store/auth";

// 登录 / 注册页 —— 单表单双模式切换。开放注册(首个账号自动成为管理员)。
export default function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败,请重试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative z-10 flex h-screen items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm rounded-xl border border-subtle bg-panel p-6 shadow-xl"
      >
        <div className="mb-5 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-dim">
            <Activity size={18} strokeWidth={2.4} style={{ color: "var(--accent)" }} />
          </div>
          <div>
            <div className="font-display text-base font-700 tracking-wide text-ink">量化决策终端</div>
            <div className="text-2xs uppercase tracking-[0.25em] text-ink-3">STOCK RESEARCH AGENT</div>
          </div>
        </div>

        {/* 模式切换 */}
        <div className="mb-4 flex rounded-md border border-subtle bg-inset p-0.5">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError("");
              }}
              className="flex-1 rounded-sm py-1.5 text-xs font-600 transition-colors"
              style={{
                background: mode === m ? "var(--bg-elevated)" : "transparent",
                color: mode === m ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-ink-3">用户名</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="rounded-md border border-subtle bg-inset px-3 py-2 font-mono text-sm text-ink outline-none focus:border-strong"
              placeholder="3-32 位字母/数字/_.-"
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-ink-3">密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="rounded-md border border-subtle bg-inset px-3 py-2 font-mono text-sm text-ink outline-none focus:border-strong"
              placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
              required
            />
          </label>

          {error && (
            <div className="rounded-md border px-3 py-2 text-2xs" style={{ borderColor: "var(--down)", color: "var(--down)" }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-1 flex items-center justify-center gap-1.5 rounded-md py-2 text-sm font-600 text-black transition-opacity disabled:opacity-60"
            style={{ background: "var(--accent)" }}
          >
            {busy ? (
              <Loader2 size={15} className="animate-spin" />
            ) : mode === "login" ? (
              <LogIn size={15} />
            ) : (
              <UserPlus size={15} />
            )}
            {mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>

        <p className="mt-4 text-center text-2xs text-ink-3">
          {mode === "login" ? "还没有账号?" : "已有账号?"}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
            className="ml-1 font-600"
            style={{ color: "var(--accent)" }}
          >
            {mode === "login" ? "去注册" : "去登录"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}

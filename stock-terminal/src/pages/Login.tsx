import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Alert, Button, Card, Form, Input, Segmented } from "antd";
import { LockOutlined, StockOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/store/auth";

// 登录 / 注册页(antd Form) —— 单表单双模式切换。开放注册(首个账号自动成为管理员)。
export default function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onFinish(values: { username: string; password: string }) {
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(values.username.trim(), values.password);
      } else {
        await register(values.username.trim(), values.password);
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
        className="w-full max-w-sm"
      >
        <Card styles={{ body: { padding: 24 } }} style={{ boxShadow: "var(--shadow-pop)" }}>
          <div className="mb-5 flex items-center gap-2.5">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-md"
              style={{ background: "var(--accent-dim)", boxShadow: "inset 0 0 0 1px rgba(130,71,255,0.35)" }}
            >
              <StockOutlined style={{ fontSize: 18, color: "var(--accent)" }} />
            </div>
            <div>
              <div className="font-display text-base font-bold tracking-wide text-ink">AI 投研终端</div>
              <div className="text-2xs uppercase tracking-[0.22em] text-ink-3">Stock Research Terminal</div>
            </div>
          </div>

          <Segmented
            block
            value={mode}
            onChange={(v) => {
              setMode(v as "login" | "register");
              setError("");
            }}
            options={[
              { label: "登录", value: "login" },
              { label: "注册", value: "register" },
            ]}
            style={{ marginBottom: 16 }}
          />

          <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
            <Form.Item
              name="username"
              label={<span className="text-2xs text-ink-3">用户名</span>}
              rules={[
                { required: true, message: "请输入用户名" },
                { pattern: /^[\w.-]{3,32}$/, message: "3-32 位字母/数字/_.-" },
              ]}
            >
              <Input
                prefix={<UserOutlined style={{ color: "var(--text-muted)" }} />}
                placeholder="3-32 位字母/数字/_.-"
                autoComplete="username"
              />
            </Form.Item>
            <Form.Item
              name="password"
              label={<span className="text-2xs text-ink-3">密码</span>}
              rules={[
                { required: true, message: "请输入密码" },
                ...(mode === "register" ? [{ min: 6, message: "至少 6 位" }] : []),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </Form.Item>

            {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

            <Button type="primary" htmlType="submit" block loading={busy}>
              {mode === "login" ? "登录" : "注册并登录"}
            </Button>
          </Form>

          <p className="mb-0 mt-4 text-center text-2xs text-ink-3">
            {mode === "login" ? "还没有账号?" : "已有账号?"}
            <Button
              type="link"
              size="small"
              style={{ fontSize: 11, paddingInline: 4 }}
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
            >
              {mode === "login" ? "去注册" : "去登录"}
            </Button>
          </p>
        </Card>
      </motion.div>
    </div>
  );
}

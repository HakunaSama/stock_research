import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Alert, Button, Card, Form, Input, Segmented } from "antd";
import {
  LockOutlined,
  MailOutlined,
  SafetyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { resetPassword, sendEmailCode } from "@/lib/auth";
import type { CodePurpose } from "@/lib/auth";
import { useAuth } from "@/store/auth";
import BrandMark from "@/components/BrandMark";

type Mode = "login" | "register" | "reset";

// 发送验证码按钮:调 send-code,成功后 60s 倒计时;开发模式回显 dev_code。
function SendCodeButton({
  getEmail,
  purpose,
  onDevCode,
  onError,
}: {
  getEmail: () => string;
  purpose: CodePurpose;
  onDevCode: (code: string) => void;
  onError: (msg: string) => void;
}) {
  const [countdown, setCountdown] = useState(0);
  const [sending, setSending] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

  function startCountdown(seconds: number) {
    setCountdown(seconds);
    timer.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1 && timer.current) clearInterval(timer.current);
        return Math.max(0, c - 1);
      });
    }, 1000);
  }

  async function onSend() {
    const email = getEmail().trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      onError("请先输入正确的邮箱地址");
      return;
    }
    setSending(true);
    onError("");
    try {
      const res = await sendEmailCode(email, purpose);
      startCountdown(res.resend_after || 60);
      if (res.dev_code) onDevCode(res.dev_code);
    } catch (e) {
      onError(e instanceof Error ? e.message : "验证码发送失败");
    } finally {
      setSending(false);
    }
  }

  return (
    <Button onClick={() => void onSend()} loading={sending} disabled={countdown > 0}>
      {countdown > 0 ? `${countdown}s 后重发` : "获取验证码"}
    </Button>
  );
}

// 登录 / 邮箱注册 / 找回密码 —— 单卡片三模式。
// 注册与找回均需邮箱验证码;未配置 SMTP 时后端回显验证码(开发模式提示)。
export default function Login() {
  const navigate = useNavigate();
  const { login, register, config } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();

  function switchMode(next: Mode) {
    setMode(next);
    setError("");
    setInfo("");
    form.resetFields(["code", "password", "new_password"]);
  }

  function onDevCode(code: string) {
    form.setFieldValue("code", code);
    setInfo(`开发模式(未配置 SMTP):验证码 ${code} 已自动填入`);
  }

  async function onFinish(values: Record<string, string>) {
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(values.account.trim(), values.password);
        navigate("/", { replace: true });
      } else if (mode === "register") {
        await register(values.email.trim(), values.code.trim(), values.password);
        navigate("/", { replace: true });
      } else {
        await resetPassword(values.email.trim(), values.code.trim(), values.new_password);
        switchMode("login");
        setInfo("密码已重置,请用新密码登录。");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败,请重试");
    } finally {
      setBusy(false);
    }
  }

  const emailField = (
    <Form.Item
      name="email"
      label={<span className="text-2xs text-ink-3">邮箱</span>}
      rules={[
        { required: true, message: "请输入邮箱" },
        { type: "email", message: "邮箱格式不正确" },
      ]}
    >
      <Input
        prefix={<MailOutlined style={{ color: "var(--text-muted)" }} />}
        placeholder="you@example.com"
        autoComplete="email"
      />
    </Form.Item>
  );

  const codeField = (purpose: CodePurpose) => (
    <Form.Item label={<span className="text-2xs text-ink-3">邮箱验证码</span>} required>
      <div className="flex gap-2">
        <Form.Item name="code" noStyle rules={[{ required: true, message: "请输入验证码" }]}>
          <Input
            prefix={<SafetyOutlined style={{ color: "var(--text-muted)" }} />}
            placeholder="6 位数字"
            maxLength={6}
          />
        </Form.Item>
        <SendCodeButton
          getEmail={() => String(form.getFieldValue("email") ?? "")}
          purpose={purpose}
          onDevCode={onDevCode}
          onError={setError}
        />
      </div>
    </Form.Item>
  );

  return (
    <div className="relative z-10 flex min-h-dvh items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm"
      >
        <Card styles={{ body: { padding: 24 } }} style={{ boxShadow: "var(--shadow-pop)" }}>
          <div className="mb-5">
            <BrandMark size="lg" />
          </div>

          {mode !== "reset" && (
            <Segmented
              block
              value={mode}
              onChange={(v) => switchMode(v as Mode)}
              options={[
                { label: "登录", value: "login" },
                { label: "邮箱注册", value: "register" },
              ]}
              style={{ marginBottom: 16 }}
            />
          )}
          {mode === "reset" && (
            <div className="mb-4 text-sm font-semibold text-ink">找回密码</div>
          )}

          <Form form={form} layout="vertical" onFinish={(v) => void onFinish(v)} requiredMark={false}>
            {mode === "login" && (
              <>
                <Form.Item
                  name="account"
                  label={<span className="text-2xs text-ink-3">邮箱 / 用户名</span>}
                  rules={[{ required: true, message: "请输入邮箱或用户名" }]}
                >
                  <Input
                    prefix={<UserOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="邮箱或用户名"
                    autoComplete="username"
                  />
                </Form.Item>
                <Form.Item
                  name="password"
                  label={<span className="text-2xs text-ink-3">密码</span>}
                  rules={[{ required: true, message: "请输入密码" }]}
                  style={{ marginBottom: 8 }}
                >
                  <Input.Password
                    prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="请输入密码"
                    autoComplete="current-password"
                  />
                </Form.Item>
                <div className="mb-3 text-right">
                  <Button
                    type="link"
                    size="small"
                    style={{ fontSize: 11, paddingInline: 0 }}
                    onClick={() => switchMode("reset")}
                  >
                    忘记密码?
                  </Button>
                </div>
              </>
            )}

            {mode === "register" && (
              <>
                {emailField}
                {codeField("register")}
                <Form.Item
                  name="password"
                  label={<span className="text-2xs text-ink-3">设置密码</span>}
                  rules={[
                    { required: true, message: "请设置密码" },
                    { min: 8, message: "至少 8 位" },
                  ]}
                >
                  <Input.Password
                    prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="至少 8 位"
                    autoComplete="new-password"
                  />
                </Form.Item>
              </>
            )}

            {mode === "reset" && (
              <>
                {emailField}
                {codeField("reset")}
                <Form.Item
                  name="new_password"
                  label={<span className="text-2xs text-ink-3">新密码</span>}
                  rules={[
                    { required: true, message: "请设置新密码" },
                    { min: 8, message: "至少 8 位" },
                  ]}
                >
                  <Input.Password
                    prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="至少 8 位"
                    autoComplete="new-password"
                  />
                </Form.Item>
              </>
            )}

            {config.email_dev_mode && mode !== "login" && !info && (
              <Alert
                type="info"
                showIcon
                message="当前为开发模式(未配置 SMTP),点击「获取验证码」后验证码将自动填入。"
                style={{ marginBottom: 16, fontSize: 12 }}
              />
            )}
            {info && <Alert type="success" showIcon message={info} style={{ marginBottom: 16 }} />}
            {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

            <Button type="primary" htmlType="submit" block loading={busy}>
              {mode === "login" ? "登录" : mode === "register" ? "注册并登录" : "重置密码"}
            </Button>
          </Form>

          <p className="mb-0 mt-4 text-center text-2xs text-ink-3">
            {mode === "login" && (
              <>
                还没有账号?
                <Button
                  type="link"
                  size="small"
                  style={{ fontSize: 11, paddingInline: 4 }}
                  onClick={() => switchMode("register")}
                >
                  邮箱注册
                </Button>
              </>
            )}
            {mode === "register" && (
              <>
                已有账号?
                <Button
                  type="link"
                  size="small"
                  style={{ fontSize: 11, paddingInline: 4 }}
                  onClick={() => switchMode("login")}
                >
                  去登录
                </Button>
              </>
            )}
            {mode === "reset" && (
              <Button
                type="link"
                size="small"
                style={{ fontSize: 11, paddingInline: 4 }}
                onClick={() => switchMode("login")}
              >
                返回登录
              </Button>
            )}
          </p>
        </Card>
      </motion.div>
    </div>
  );
}

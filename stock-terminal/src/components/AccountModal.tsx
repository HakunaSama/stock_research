import { useEffect, useRef, useState } from "react";
import { Alert, Button, Form, Input, Modal, Tabs, Tag, message } from "antd";
import { LockOutlined, MailOutlined, SafetyOutlined } from "@ant-design/icons";
import { bindEmail, changePassword, sendEmailCode } from "@/lib/auth";
import { useAuth } from "@/store/auth";

// 账号与安全:绑定/换绑邮箱(邮箱验证码) + 修改密码(改完踢掉其他会话)。
export default function AccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, config, setUser } = useAuth();
  const [emailForm] = Form.useForm();
  const [pwdForm] = Form.useForm();
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  const [countdown, setCountdown] = useState(0);
  const [sending, setSending] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

  function reset() {
    setErr("");
    setInfo("");
    emailForm.resetFields();
    pwdForm.resetFields();
  }

  async function onSendCode() {
    const email = String(emailForm.getFieldValue("email") ?? "").trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setErr("请先输入正确的邮箱地址");
      return;
    }
    setSending(true);
    setErr("");
    try {
      const res = await sendEmailCode(email, "bind");
      setCountdown(res.resend_after || 60);
      timer.current = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1 && timer.current) clearInterval(timer.current);
          return Math.max(0, c - 1);
        });
      }, 1000);
      if (res.dev_code) {
        emailForm.setFieldValue("code", res.dev_code);
        setInfo(`开发模式(未配置 SMTP):验证码 ${res.dev_code} 已自动填入`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "验证码发送失败");
    } finally {
      setSending(false);
    }
  }

  async function onBind(values: { email: string; code: string }) {
    setBusy(true);
    setErr("");
    try {
      const updated = await bindEmail(values.email.trim(), values.code.trim());
      setUser(updated);
      message.success("邮箱绑定成功");
      emailForm.resetFields();
      setInfo("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "绑定失败");
    } finally {
      setBusy(false);
    }
  }

  async function onChangePwd(values: { old_password: string; new_password: string }) {
    setBusy(true);
    setErr("");
    try {
      await changePassword(values.old_password, values.new_password);
      message.success("密码已修改,其他设备已退出登录");
      pwdForm.resetFields();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onCancel={() => {
        reset();
        onClose();
      }}
      footer={null}
      title="账号与安全"
      width={420}
      destroyOnHidden
    >
      <div className="mb-3 text-xs text-ink-3">
        当前邮箱:
        {user?.email ? (
          <span className="ml-1 text-ink-2">
            {user.email}
            {user.email_verified && (
              <Tag color="green" style={{ marginLeft: 6, fontSize: 10, lineHeight: "16px" }}>
                已验证
              </Tag>
            )}
          </span>
        ) : (
          <span className="ml-1">未绑定(绑定后可用邮箱登录、找回密码)</span>
        )}
      </div>

      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}
      {info && <Alert type="info" showIcon message={info} style={{ marginBottom: 12 }} />}

      <Tabs
        size="small"
        onChange={() => {
          setErr("");
          setInfo("");
        }}
        items={[
          {
            key: "email",
            label: user?.email ? "换绑邮箱" : "绑定邮箱",
            children: (
              <Form form={emailForm} layout="vertical" onFinish={(v) => void onBind(v)} requiredMark={false}>
                <Form.Item
                  name="email"
                  label={<span className="text-2xs text-ink-3">新邮箱</span>}
                  rules={[
                    { required: true, message: "请输入邮箱" },
                    { type: "email", message: "邮箱格式不正确" },
                  ]}
                >
                  <Input
                    prefix={<MailOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="you@example.com"
                  />
                </Form.Item>
                <Form.Item label={<span className="text-2xs text-ink-3">邮箱验证码</span>} required>
                  <div className="flex gap-2">
                    <Form.Item name="code" noStyle rules={[{ required: true, message: "请输入验证码" }]}>
                      <Input
                        prefix={<SafetyOutlined style={{ color: "var(--text-muted)" }} />}
                        placeholder="6 位数字"
                        maxLength={6}
                      />
                    </Form.Item>
                    <Button onClick={() => void onSendCode()} loading={sending} disabled={countdown > 0}>
                      {countdown > 0 ? `${countdown}s 后重发` : "获取验证码"}
                    </Button>
                  </div>
                </Form.Item>
                {config.email_dev_mode && (
                  <div className="mb-3 text-2xs text-ink-3">
                    开发模式:未配置 SMTP,验证码会自动填入。
                  </div>
                )}
                <Button type="primary" htmlType="submit" block loading={busy}>
                  确认绑定
                </Button>
              </Form>
            ),
          },
          {
            key: "password",
            label: "修改密码",
            children: (
              <Form form={pwdForm} layout="vertical" onFinish={(v) => void onChangePwd(v)} requiredMark={false}>
                <Form.Item
                  name="old_password"
                  label={<span className="text-2xs text-ink-3">原密码</span>}
                  rules={[{ required: true, message: "请输入原密码" }]}
                >
                  <Input.Password
                    prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="当前使用的密码"
                    autoComplete="current-password"
                  />
                </Form.Item>
                <Form.Item
                  name="new_password"
                  label={<span className="text-2xs text-ink-3">新密码</span>}
                  rules={[
                    { required: true, message: "请设置新密码" },
                    { min: 6, message: "至少 6 位" },
                  ]}
                >
                  <Input.Password
                    prefix={<LockOutlined style={{ color: "var(--text-muted)" }} />}
                    placeholder="至少 6 位"
                    autoComplete="new-password"
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" block loading={busy}>
                  确认修改
                </Button>
              </Form>
            ),
          },
        ]}
      />
    </Modal>
  );
}

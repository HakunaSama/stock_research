import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Tabs,
  Tag,
  message,
} from "antd";
import {
  CameraOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  DesktopOutlined,
  DisconnectOutlined,
  LockOutlined,
  MailOutlined,
  MobileOutlined,
  SafetyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  bindEmail,
  changePassword,
  deleteAvatar,
  fetchSessions,
  revokeOtherSessions,
  revokeSession,
  sendEmailCode,
  updateProfile,
  uploadAvatar,
  type ActiveSession,
} from "@/lib/auth";
import { fmtTs } from "@/lib/utils";
import { useAuth } from "@/store/auth";

type ProfileValues = {
  username: string;
  display_name: string;
  bio: string;
  current_password?: string;
};

function deviceLabel(userAgent: string) {
  const mobile = /iPhone|iPad|Android|Mobile/i.test(userAgent);
  const os = /iPhone|iPad/i.test(userAgent)
    ? "iPhone / iPad"
    : /Android/i.test(userAgent)
      ? "Android"
      : /Macintosh/i.test(userAgent)
        ? "macOS"
        : /Windows/i.test(userAgent)
          ? "Windows"
          : /Linux/i.test(userAgent)
            ? "Linux"
            : "未知设备";
  const browser = /Edg\//i.test(userAgent)
    ? "Edge"
    : /Chrome\//i.test(userAgent)
      ? "Chrome"
      : /Safari\//i.test(userAgent)
        ? "Safari"
        : /Firefox\//i.test(userAgent)
          ? "Firefox"
          : "浏览器";
  return { mobile, text: `${os} · ${browser}` };
}

// 完整用户中心：个人资料 / 已验证邮箱 / 密码 / 活跃设备。
export default function AccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, config, setUser } = useAuth();
  const [profileForm] = Form.useForm<ProfileValues>();
  const [emailForm] = Form.useForm();
  const [pwdForm] = Form.useForm();
  const avatarInput = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const [tab, setTab] = useState("profile");
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [sending, setSending] = useState(false);
  const [sessions, setSessions] = useState<ActiveSession[]>([]);
  const [sessionsBusy, setSessionsBusy] = useState(false);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

  useEffect(() => {
    if (!open || !user) return;
    profileForm.setFieldsValue({
      username: user.username,
      display_name: user.display_name || user.username,
      bio: user.bio || "",
      current_password: "",
    });
  }, [open, profileForm, user]);

  async function loadSessions() {
    setSessionsBusy(true);
    try {
      setSessions(await fetchSessions());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "设备列表加载失败");
    } finally {
      setSessionsBusy(false);
    }
  }

  useEffect(() => {
    if (open && tab === "sessions") void loadSessions();
  }, [open, tab]);

  function clearStatus() {
    setErr("");
    setInfo("");
  }

  function reset() {
    clearStatus();
    setTab("profile");
    emailForm.resetFields();
    pwdForm.resetFields();
  }

  async function onSaveProfile(values: ProfileValues) {
    setBusy(true);
    clearStatus();
    try {
      const updated = await updateProfile(values);
      setUser(updated);
      profileForm.setFieldValue("current_password", "");
      message.success("个人资料已保存");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "资料保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function onAvatarFile(file: File | undefined) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setErr("头像仅支持 JPG、PNG 或 WebP");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setErr("头像不能超过 5MB");
      return;
    }
    setAvatarBusy(true);
    clearStatus();
    try {
      setUser(await uploadAvatar(file));
      message.success("头像已更新");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "头像上传失败");
    } finally {
      setAvatarBusy(false);
      if (avatarInput.current) avatarInput.current.value = "";
    }
  }

  async function onDeleteAvatar() {
    setAvatarBusy(true);
    clearStatus();
    try {
      setUser(await deleteAvatar());
      message.success("头像已移除");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "头像移除失败");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function onSendCode() {
    const email = String(emailForm.getFieldValue("email") ?? "").trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setErr("请先输入正确的邮箱地址");
      return;
    }
    setSending(true);
    clearStatus();
    try {
      const res = await sendEmailCode(email, "bind");
      setCountdown(res.resend_after || 60);
      timer.current = setInterval(() => {
        setCountdown((current) => {
          if (current <= 1 && timer.current) clearInterval(timer.current);
          return Math.max(0, current - 1);
        });
      }, 1000);
      if (res.dev_code) {
        emailForm.setFieldValue("code", res.dev_code);
        setInfo(`开发模式：验证码 ${res.dev_code} 已自动填入`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "验证码发送失败");
    } finally {
      setSending(false);
    }
  }

  async function onBind(values: { email: string; code: string }) {
    setBusy(true);
    clearStatus();
    try {
      setUser(await bindEmail(values.email.trim(), values.code.trim()));
      message.success("邮箱绑定成功");
      emailForm.resetFields();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "绑定失败");
    } finally {
      setBusy(false);
    }
  }

  async function onChangePwd(values: { old_password: string; new_password: string }) {
    setBusy(true);
    clearStatus();
    try {
      await changePassword(values.old_password, values.new_password);
      message.success("密码已修改，其他设备已退出登录");
      pwdForm.resetFields();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    clearStatus();
    try {
      await revokeSession(id);
      await loadSessions();
      message.success("该设备已退出登录");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "移除设备失败");
    }
  }

  async function onRevokeOthers() {
    clearStatus();
    try {
      await revokeOtherSessions();
      await loadSessions();
      message.success("其他设备均已退出登录");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    }
  }

  const profileContent = (
    <div className="grid gap-5 md:grid-cols-[150px_minmax(0,1fr)]">
      <div className="flex flex-col items-center gap-2 rounded-lg border border-subtle bg-inset p-4 text-center">
        <Avatar
          size={82}
          src={user?.avatar_url || undefined}
          icon={!user?.avatar_url ? <UserOutlined /> : undefined}
          style={{ background: "var(--accent-dim)", color: "var(--accent)", fontSize: 30 }}
        />
        <input
          ref={avatarInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(event) => void onAvatarFile(event.target.files?.[0])}
        />
        <Button size="small" icon={<CameraOutlined />} loading={avatarBusy} onClick={() => avatarInput.current?.click()}>
          更换头像
        </Button>
        {user?.avatar_url && (
          <Popconfirm title="移除当前头像？" onConfirm={() => void onDeleteAvatar()}>
            <Button size="small" type="text" danger icon={<DeleteOutlined />}>移除</Button>
          </Popconfirm>
        )}
        <span className="text-2xs leading-relaxed text-ink-3">JPG / PNG / WebP<br />最大 5MB</span>
      </div>

      <Form form={profileForm} layout="vertical" onFinish={(values) => void onSaveProfile(values)} requiredMark={false}>
        <Form.Item name="display_name" label="展示名称" rules={[{ required: true }, { max: 40 }]}>
          <Input prefix={<UserOutlined />} placeholder="在界面和社区中显示的名称" maxLength={40} showCount />
        </Form.Item>
        <Form.Item
          name="username"
          label="登录用户名"
          extra="3–32 位，仅支持字母、数字、下划线、点和短横线；修改后登录账号同步变化。"
          rules={[
            { required: true },
            { pattern: /^[A-Za-z0-9_.-]{3,32}$/, message: "用户名格式不正确" },
          ]}
        >
          <Input prefix={<UserOutlined />} autoComplete="username" />
        </Form.Item>
        <Form.Item name="bio" label="个人简介" rules={[{ max: 160 }]}>
          <Input.TextArea rows={3} maxLength={160} showCount placeholder="介绍你的投资偏好或研究方向" />
        </Form.Item>
        <Form.Item
          noStyle
          shouldUpdate={(before, after) => before.username !== after.username}
        >
          {({ getFieldValue }) => getFieldValue("username") !== user?.username ? (
            <Form.Item name="current_password" label="当前密码" rules={[{ required: true, message: "修改登录用户名需要验证密码" }]}>
              <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
            </Form.Item>
          ) : null}
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>保存个人资料</Button>
      </Form>
    </div>
  );

  const emailContent = (
    <div>
      <div className="mb-4 rounded-md border border-subtle bg-inset px-3 py-2 text-xs text-ink-2">
        当前邮箱：{user?.email || "未绑定"}
        {user?.email_verified && <Tag color="green" className="ml-2"><CheckCircleOutlined /> 已验证</Tag>}
      </div>
      <Form form={emailForm} layout="vertical" onFinish={(values) => void onBind(values)} requiredMark={false}>
        <Form.Item name="email" label="新邮箱" rules={[{ required: true }, { type: "email", message: "邮箱格式不正确" }]}>
          <Input prefix={<MailOutlined />} placeholder="you@example.com" autoComplete="email" />
        </Form.Item>
        <Form.Item label="邮箱验证码" required>
          <div className="flex gap-2">
            <Form.Item name="code" noStyle rules={[{ required: true, message: "请输入验证码" }]}>
              <Input prefix={<SafetyOutlined />} placeholder="6 位数字" maxLength={6} />
            </Form.Item>
            <Button onClick={() => void onSendCode()} loading={sending} disabled={countdown > 0}>
              {countdown > 0 ? `${countdown}s 后重发` : "获取验证码"}
            </Button>
          </div>
        </Form.Item>
        {config.email_dev_mode && <div className="mb-3 text-2xs text-ink-3">本地开发模式下验证码会自动填入。</div>}
        <Button type="primary" htmlType="submit" loading={busy}>{user?.email ? "确认换绑" : "确认绑定"}</Button>
      </Form>
    </div>
  );

  const passwordContent = (
    <Form form={pwdForm} layout="vertical" onFinish={(values) => void onChangePwd(values)} requiredMark={false}>
      <Alert className="mb-4" type="info" showIcon message="密码修改后，除当前设备外的其他登录会话会立即失效。" />
      <Form.Item name="old_password" label="当前密码" rules={[{ required: true }]}>
        <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
      </Form.Item>
      <Form.Item name="new_password" label="新密码" rules={[{ required: true }, { min: 8, message: "至少 8 位" }]}>
        <Input.Password prefix={<LockOutlined />} placeholder="至少 8 位" autoComplete="new-password" />
      </Form.Item>
      <Button type="primary" htmlType="submit" loading={busy}>修改密码</Button>
    </Form>
  );

  const sessionsContent = (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-xs text-ink-3">查看并管理仍可访问此账号的设备。</span>
        <Popconfirm title="让其他所有设备退出登录？" onConfirm={() => void onRevokeOthers()}>
          <Button size="small" danger icon={<DisconnectOutlined />}>退出其他设备</Button>
        </Popconfirm>
      </div>
      <div className="overflow-hidden rounded-lg border border-subtle">
        {sessionsBusy ? (
          <div className="p-6 text-center text-xs text-ink-3">正在加载设备…</div>
        ) : sessions.length === 0 ? (
          <div className="p-6 text-center text-xs text-ink-3">暂无活跃会话</div>
        ) : sessions.map((session) => {
          const device = deviceLabel(session.user_agent);
          return (
            <div key={session.id} className="flex items-center gap-3 border-b border-subtle px-3 py-3 last:border-0">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-inset text-ink-3">
                {device.mobile ? <MobileOutlined /> : <DesktopOutlined />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                  {device.text}
                  {session.current && <Tag color="purple">当前设备</Tag>}
                </div>
                <div className="mt-0.5 text-2xs text-ink-3">
                  IP {session.ip_address || "未知"} · 最近活动 {fmtTs(session.last_seen_at)}
                </div>
              </div>
              {!session.current && (
                <Popconfirm title="让这台设备退出登录？" onConfirm={() => void onRevoke(session.id)}>
                  <Button size="small" type="text" danger>移除</Button>
                </Popconfirm>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      onCancel={() => { reset(); onClose(); }}
      footer={null}
      title="个人中心"
      width="min(700px, calc(100vw - 20px))"
      destroyOnHidden
    >
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-ink-3">
        <span>账号 ID：{user?.id}</span>
        <span>注册于 {user ? fmtTs(user.created_at) : "-"}</span>
        {user?.is_admin && <Tag color="purple">管理员</Tag>}
      </div>
      {err && <Alert type="error" showIcon message={err} className="mb-3" closable onClose={() => setErr("")} />}
      {info && <Alert type="info" showIcon message={info} className="mb-3" />}
      <Tabs
        activeKey={tab}
        onChange={(key) => { setTab(key); clearStatus(); }}
        items={[
          { key: "profile", label: "个人资料", children: profileContent },
          { key: "email", label: "邮箱", children: emailContent },
          { key: "password", label: "密码", children: passwordContent },
          { key: "sessions", label: "登录设备", children: sessionsContent },
        ]}
      />
    </Modal>
  );
}

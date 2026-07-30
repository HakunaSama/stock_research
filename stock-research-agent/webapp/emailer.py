"""Email delivery — verification codes over SMTP, with an explicit dev mode.

Configuration (env):

    SMTP_HOST / SMTP_PORT   — server, e.g. smtp.qq.com:465
    SMTP_USER / SMTP_PASS   — login (for QQ/163 use the authorization code)
    SMTP_FROM               — From header, defaults to SMTP_USER
    SMTP_SSL                — "1" (default) = implicit SSL (port 465),
                              "0" = STARTTLS (port 587)

When SMTP is NOT configured the app stays fully usable for development:
``send_code`` logs the code to the server log and returns it, and the auth
routes surface it in the API response (``dev_code``) so the flow can be
exercised end-to-end. The /api/config flag ``email_dev_mode`` tells the SPA
to show a hint. Configure SMTP before going live.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

log = logging.getLogger("webapp.emailer")

APP_NAME = os.environ.get("APP_NAME", "AI 投研终端")

_PURPOSE_LABEL = {
    "register": "注册账号",
    "reset": "重置密码",
    "bind": "绑定邮箱",
}


class EmailError(RuntimeError):
    """SMTP delivery failed (config or transport)."""


def _smtp_config() -> Optional[dict]:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    if not (host and user and password):
        return None
    # Compose may inject SMTP_FROM="" even when unset; empty From makes QQ
    # SMTP reply 502 "Invalid paramenters". Always fall back to SMTP_USER.
    from_addr = os.environ.get("SMTP_FROM", "").strip() or user
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", 465)),
        "user": user,
        "password": password,
        "from": from_addr,
        "ssl": os.environ.get("SMTP_SSL", "1") in ("1", "true", "True"),
    }


def email_configured() -> bool:
    """True when a real SMTP transport is configured (production mode)."""
    return _smtp_config() is not None


def _render_code_mail(purpose: str, code: str, ttl_minutes: int) -> tuple[str, str]:
    action = _PURPOSE_LABEL.get(purpose, "身份验证")
    subject = f"【{APP_NAME}】{action}验证码：{code}"
    body = (
        f"您好，\n\n"
        f"您正在进行「{action}」操作，本次验证码为：\n\n"
        f"    {code}\n\n"
        f"验证码 {ttl_minutes} 分钟内有效，请勿泄露给任何人。\n"
        f"如果这不是您本人的操作，请忽略本邮件。\n\n"
        f"—— {APP_NAME}"
    )
    return subject, body


_send_lock = threading.Lock()


def send_code(to_email: str, purpose: str, code: str, ttl_minutes: int = 10) -> Optional[str]:
    """Deliver a verification code.

    Returns None on real SMTP delivery; returns the code itself in dev mode
    (no SMTP configured) so callers can expose it for local testing.

    Raises EmailError when SMTP is configured but delivery fails.
    """
    cfg = _smtp_config()
    if cfg is None:
        log.warning("[DEV] email code for %s (%s): %s", to_email, purpose, code)
        return code

    subject, body = _render_code_mail(purpose, code, ttl_minutes)
    msg = MIMEText(body, "plain", "utf-8")
    # Encode headers explicitly — QQ SMTP is picky about bare non-ASCII / empty From.
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(APP_NAME, "utf-8")), cfg["from"]))
    msg["To"] = formataddr(("", to_email))

    try:
        # smtplib is not thread-safe per-connection; serialize sends (low volume).
        with _send_lock:
            if cfg["ssl"]:
                server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15)
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
                server.starttls()
            try:
                server.login(cfg["user"], cfg["password"])
                # Envelope sender must match the authenticated QQ mailbox.
                server.sendmail(cfg["from"], [to_email], msg.as_string())
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001
                    server.close()
    except Exception as e:  # noqa: BLE001 — surface any transport failure uniformly
        log.error("send email to %s failed: %s", to_email, e)
        raise EmailError(f"邮件发送失败：{e}") from e
    return None

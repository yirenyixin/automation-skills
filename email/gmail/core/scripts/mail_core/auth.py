"""Gmail IMAP/SMTP app-password authentication helpers."""

from __future__ import annotations

from .common import fail


def imap_login(client, config: dict) -> None:
    try:
        status, _ = client.login(config["account"]["email"], config["app_password"])
    except Exception:
        fail("Gmail IMAP 应用专用密码认证失败。请检查本地配置、两步验证和应用专用密码。")
    if status != "OK":
        fail("Gmail IMAP 应用专用密码认证失败。请检查本地配置、两步验证和应用专用密码。")


def smtp_login(client, config: dict) -> None:
    try:
        reply = client.login(config["account"]["email"], config["app_password"])
    except Exception:
        fail("Gmail SMTP 应用专用密码认证失败。请检查本地配置、两步验证和应用专用密码。")
    if isinstance(reply, tuple) and reply and reply[0] != 235:
        fail("Gmail SMTP 应用专用密码认证失败。请检查本地配置、两步验证和应用专用密码。")

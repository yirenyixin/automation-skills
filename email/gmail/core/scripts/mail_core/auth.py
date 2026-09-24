"""Gmail XOAUTH2 authentication helpers; never log token values."""

from __future__ import annotations

import base64

from .common import fail
from .oauth import get_access_token


def _payload(config: dict) -> bytes:
    token = get_access_token(config["oauth"])
    return f"user={config['account']['email']}\x01auth=Bearer {token}\x01\x01".encode()


def imap_login(client, config: dict) -> None:
    try:
        status, _ = client.authenticate("XOAUTH2", lambda _challenge: _payload(config))
    except Exception:
        fail("Gmail IMAP OAuth 认证失败。请检查授权范围和本地令牌。")
    if status != "OK":
        fail("Gmail IMAP OAuth 认证失败。请检查授权范围和本地令牌。")


def smtp_login(client, config: dict) -> None:
    try:
        client.ehlo()
        status, _ = client.docmd("AUTH", "XOAUTH2 " + base64.b64encode(_payload(config)).decode("ascii"))
    except Exception:
        fail("Gmail SMTP OAuth 认证失败。请检查授权范围和本地令牌。")
    if status != 235:
        fail("Gmail SMTP OAuth 认证失败。请检查授权范围和本地令牌。")

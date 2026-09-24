"""Minimal local OAuth 2.0 refresh support for Gmail IMAP/SMTP."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .common import fail


TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _access_token(token: dict) -> str:
    value = token.get("access_token") or token.get("token")
    return value if isinstance(value, str) else ""


def get_access_token(oauth: dict) -> str:
    token = oauth["token"]
    current = _access_token(token)
    expires_at = token.get("expires_at")
    if current and (not isinstance(expires_at, (int, float)) or expires_at > time.time() + 60):
        return current
    refresh_token = token.get("refresh_token")
    client = oauth["client"]
    if not isinstance(refresh_token, str) or not refresh_token:
        fail("Gmail OAuth 令牌缺少刷新令牌；请在用户完成浏览器授权后重新生成令牌。")
    body = urlencode({"client_id": client.get("client_id", ""), "client_secret": client.get("client_secret", ""), "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    try:
        request = Request(TOKEN_ENDPOINT, data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError):
        fail("Gmail OAuth 刷新失败。请检查网络、客户端配置和授权状态。")
    refreshed = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(refreshed, str) or not refreshed:
        fail("Gmail OAuth 刷新被拒绝。请重新完成用户浏览器授权。")
    token["access_token"] = refreshed
    token["expires_at"] = time.time() + int(data.get("expires_in", 3600))
    try:
        Path(oauth["token_path"]).write_text(json.dumps(token, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        fail("Gmail OAuth 令牌已刷新，但无法安全写回本地令牌文件。")
    return refreshed

#!/usr/bin/env python3
"""Interactive local OAuth authorization for Gmail. Never prints or logs tokens."""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://mail.google.com/"


def fail(message: str) -> None:
    raise SystemExit(f"错误：{message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Gmail 本地浏览器 OAuth 授权")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("timeout-seconds 必须是正整数。")
    try:
        raw = json.loads((ROOT / "config" / "oauth-client.json").read_text(encoding="utf-8"))
        client = raw.get("installed") or raw.get("web")
        client_id, client_secret = client["client_id"], client["client_secret"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        fail("OAuth 客户端配置缺失或无效。请先在 config/oauth-client.json 配置桌面应用客户端。")

    code_box: dict[str, str] = {}
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if query.get("code"):
                code_box["code"] = query["code"][0]
                message = "授权已接收，可以返回终端。"
            else:
                code_box["error"] = "1"
                message = "授权未完成，可以关闭此页面。"
            encoded = message.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        def log_message(self, *_args):
            pass

    server = HTTPServer(("localhost", 0), Callback)
    redirect_uri = f"http://localhost:{server.server_port}"
    url = AUTH_ENDPOINT + "?" + urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent"})
    print("请由用户在浏览器中完成 Gmail 授权；不要把密码、验证码或授权链接中的内容发送到聊天中：")
    print(url)
    server.timeout = 1
    end = time.monotonic() + args.timeout_seconds
    while "code" not in code_box and "error" not in code_box and time.monotonic() < end:
        server.handle_request()
    server.server_close()
    if "code" not in code_box:
        fail("未在等待时间内完成浏览器授权；未写入令牌。")
    body = urlencode({"code": code_box["code"], "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"}).encode()
    try:
        request = Request(TOKEN_ENDPOINT, data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError):
        fail("OAuth 令牌交换失败；未写入令牌。请检查网络和客户端设置后重新授权。")
    if not isinstance(token, dict) or not isinstance(token.get("access_token"), str) or not isinstance(token.get("refresh_token"), str):
        fail("OAuth 未返回可用令牌；未写入令牌。请重新授权。")
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    try:
        (ROOT / "config" / "token.json").write_text(json.dumps(token, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        fail("授权成功但无法写入本地令牌文件。")
    print("【配置完成】Gmail 本地令牌已保存；未显示令牌内容，未连接或读取邮件。")


if __name__ == "__main__":
    main()

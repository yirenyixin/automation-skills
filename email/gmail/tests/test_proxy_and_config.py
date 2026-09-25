"""Offline coverage for proxy transport and local Gmail configuration."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))

from mail_core import proxy  # noqa: E402
from mail_core.config import load_config  # noqa: E402
from mail_core.sender import send  # noqa: E402


class FakeSocket:
    def __init__(self, response: bytes = b"HTTP/1.1 200 Connection established\r\n\r\n"):
        self.response = response
        self.sent = b""
        self.closed = False

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, _size: int) -> bytes:
        response, self.response = self.response, b""
        return response

    def close(self) -> None:
        self.closed = True


class ProxyAndConfigTests(unittest.TestCase):
    def test_proxy_url_prefers_https_and_respects_bypass(self):
        with patch("mail_core.proxy.proxy_bypass", return_value=False), patch(
            "mail_core.proxy.getproxies", return_value={"http": "http://http-proxy", "https": "http://https-proxy"}
        ):
            self.assertEqual(proxy._proxy_url("imap.gmail.com"), "http://https-proxy")
        with patch("mail_core.proxy.proxy_bypass", return_value=True):
            self.assertIsNone(proxy._proxy_url("imap.gmail.com"))

    def test_http_connect_proxy_sends_encoded_credentials(self):
        connection = FakeSocket()
        with patch("mail_core.proxy.socket.create_connection", return_value=connection) as create_connection:
            result = proxy._connect_tunnel("http://user%20name:p%40ss@proxy.local:8080", "imap.gmail.com", 993, 12)
        self.assertIs(result, connection)
        create_connection.assert_called_once_with(("proxy.local", 8080), timeout=12)
        expected = base64.b64encode(b"user name:p@ss").decode()
        self.assertIn(b"CONNECT imap.gmail.com:993 HTTP/1.1", connection.sent)
        self.assertIn(f"Proxy-Authorization: Basic {expected}".encode(), connection.sent)

    def test_rejected_proxy_tunnel_is_sanitized_and_closed(self):
        connection = FakeSocket(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        with patch("mail_core.proxy.socket.create_connection", return_value=connection):
            with self.assertRaisesRegex(ValueError, "CONNECT 隧道"):
                proxy._connect_tunnel("http://proxy.local", "imap.gmail.com", 993, 5)
        self.assertTrue(connection.closed)

    def test_open_tls_socket_uses_direct_socket_without_proxy(self):
        raw, tls = object(), object()
        context = Mock()
        context.wrap_socket.return_value = tls
        with patch("mail_core.proxy._proxy_url", return_value=None), patch(
            "mail_core.proxy.socket.create_connection", return_value=raw
        ) as create_connection, patch("mail_core.proxy.ssl.create_default_context", return_value=context):
            self.assertIs(proxy.open_tls_socket("imap.gmail.com", 993, 9), tls)
        create_connection.assert_called_once_with(("imap.gmail.com", 993), timeout=9)
        context.wrap_socket.assert_called_once_with(raw, server_hostname="imap.gmail.com")

    def test_config_defaults_servers_and_removes_password_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gmail"
            (root / "config").mkdir(parents=True)
            (root / "SKILL.md").write_text("# Gmail", encoding="utf-8")
            (root / "config" / "imap-smtp.local.json").write_text(
                json.dumps({"gmail_address": "person@gmail.com", "app_password": "abcd efgh ijkl mnop"}), encoding="utf-8"
            )
            config = load_config(root / "core" / "scripts" / "mail.py")
        self.assertEqual(config["app_password"], "abcdefghijklmnop")
        self.assertEqual(config["imap"], {"host": "imap.gmail.com", "port": 993})
        self.assertEqual(config["smtp"], {"host": "smtp.gmail.com", "port": 465})

    def test_send_preview_never_constructs_transport(self):
        args = argparse.Namespace(
            to=["recipient@example.com"], cc=[], bcc=[], subject="Preview", text="Body", html=None,
            attachment=[], max_attachment_mb=20, timeout=1, confirm_send=False,
        )
        config = {"account": {"email": "me@gmail.com"}, "app_password": "test", "smtp": {"host": "localhost", "port": 465}}
        with patch("mail_core.sender.ProxySMTP_SSL") as client:
            result = send(config, args, Path.cwd())
        self.assertEqual(result["status"], "preview")
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()

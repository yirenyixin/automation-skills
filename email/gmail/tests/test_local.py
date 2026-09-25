"""Local SMTP/IMAP simulations. These tests never contact a real mailbox."""

from __future__ import annotations

import argparse
import smtplib
import sys
import tempfile
import unittest
import json
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))
from mail_core.reader import download, search  # noqa: E402
from mail_core.sender import send  # noqa: E402
from mail_core.audit import write_audit  # noqa: E402
from mail_core.config import load_config  # noqa: E402
from mail_core.storage import inspect_workspace_storage  # noqa: E402


class FakeSMTP:
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def login(self, *_): return None
    def ehlo(self): return 250, b"ok"
    def docmd(self, *_): return 235, b"accepted"
    def send_message(self, *_args, **_kwargs): return None


class FakeIMAP:
    def __init__(self, *_args, **_kwargs):
        message = EmailMessage()
        message["From"] = "finance@example.com"
        message["To"] = "me@example.com"
        message["Subject"] = "Invoice"
        message.set_content("Test message")
        self.data = message.as_bytes()
    def login(self, *_): return "OK", []
    def authenticate(self, *_): return "OK", []
    def select(self, *_args, **_kwargs): return "OK", [b"1"]
    def uid(self, command, *_args):
        return ("OK", [b"9"]) if command == "search" else ("OK", [(b"9", self.data)])
    def logout(self): return "BYE", []


class RefusingSMTP(FakeSMTP):
    def send_message(self, *_args, **_kwargs):
        raise smtplib.SMTPRecipientsRefused({"secret-bcc@example.com": (550, b"rejected")})


class AppPasswordRejectingIMAP(FakeIMAP):
    def login(self, *_): return "NO", []


class MailTests(unittest.TestCase):
    config = {"account": {"email": "me@gmail.com"}, "app_password": "test-app-password", "smtp": {"host": "localhost", "port": 465}, "imap": {"host": "localhost", "port": 993}}

    def test_smtp_preview_and_submission(self):
        args = argparse.Namespace(to=["you@example.com"], cc=[], bcc=[], subject="Test", text="Body", html=None, attachment=[], max_attachment_mb=20, timeout=1, confirm_send=False)
        self.assertEqual(send(self.config, args, Path.cwd())["status"], "preview")
        args.confirm_send = True
        with patch("mail_core.sender.ProxySMTP_SSL", return_value=FakeSMTP()):
            self.assertEqual(send(self.config, args, Path.cwd())["status"], "submitted")

    def test_imap_rule_search(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "manifest.json").write_text("{}", encoding="utf-8")
            (workspace / "rules").mkdir()
            (workspace / "rules" / "invoice.json").write_text('{"filters": {"from_contains": "finance", "subject_contains": "invoice"}}', encoding="utf-8")
            with patch("mail_core.reader.ProxyIMAP4_SSL", return_value=FakeIMAP()):
                result = search(self.config, workspace, "rules/invoice.json", 10, include_body=True)
            self.assertEqual(result[0]["uid"], "9")
            self.assertEqual(result[0]["text_preview"], "Test message")

    def test_html_only_message_has_readable_text(self):
        message = EmailMessage()
        message["From"] = "finance@example.com"
        message["To"] = "me@example.com"
        message["Subject"] = "HTML only"
        message.set_content("<style>.hidden { display: none; }</style><p>登录提醒</p><p>这是 HTML 正文。</p>", subtype="html")
        fake = FakeIMAP()
        fake.data = message.as_bytes()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "manifest.json").write_text("{}", encoding="utf-8")
            (workspace / "rules").mkdir()
            (workspace / "rules" / "html.json").write_text("{\"filters\": {}}", encoding="utf-8")
            with patch("mail_core.reader.ProxyIMAP4_SSL", return_value=fake):
                result = search(self.config, workspace, "rules/html.json", 10, include_body=True, full_body=True)
            self.assertIn("登录提醒", result[0]["text"])
            self.assertNotIn("display", result[0]["text"])
            self.assertEqual(result[0]["body_parts"][0]["content_type"], "text/html")

    def test_audit_log_uses_chinese_fields_and_omits_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "任务"
            workspace.mkdir()
            write_audit(workspace, operation="读取邮件", function="app/scripts/mail.py read", user_request="读取最新未读邮件", status="成功", inputs={"规则": "rules/latest.json"}, result={"匹配数量": 1})
            record = json.loads((workspace / "logs" / "audit.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(record["操作"], "读取邮件")
            self.assertEqual(record["状态"], "成功")
            self.assertNotIn("密码", record)

    def test_workspace_storage_reports_limit_and_cleanup_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skill"
            workspace = root / "workspaces" / "task"
            (workspace / "downloads").mkdir(parents=True)
            (root / "config").mkdir()
            (root / "config" / "workspace-policy.json").write_text('{"workspace_size_limit_mb": 1}', encoding="utf-8")
            (workspace / "downloads" / "large.bin").write_bytes(b"x" * (1024 * 1024))
            result = inspect_workspace_storage(root, workspace)
            self.assertEqual(result["状态"], "超出阈值")
            self.assertEqual(result["自动删除"], "未执行")
            self.assertTrue(result["可优先清理"][0]["路径"].endswith("downloads/large.bin"))

    def test_invalid_limits_do_not_create_imap_connection(self):
        for limit in (0, -1, True):
            with patch("mail_core.reader.ProxyIMAP4_SSL") as connection:
                with self.assertRaisesRegex(ValueError, "结果上限必须是正整数"):
                    search(self.config, Path.cwd(), "rules/unused.json", limit)
                connection.assert_not_called()

    def test_imap_connection_error_is_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "manifest.json").write_text("{}", encoding="utf-8")
            (workspace / "rules").mkdir()
            (workspace / "rules" / "test.json").write_text('{"filters": {}}', encoding="utf-8")
            with patch("mail_core.reader.ProxyIMAP4_SSL", side_effect=OSError("imap.internal.example:993")):
                with self.assertRaisesRegex(ValueError, "IMAP 网络或连接失败") as error:
                    search(self.config, workspace, "rules/test.json", 1)
            self.assertNotIn("imap.internal.example", str(error.exception))

    def test_smtp_bcc_error_is_sanitized_before_audit(self):
        args = argparse.Namespace(to=["to@example.com"], cc=[], bcc=["secret-bcc@example.com"], subject="Test", text="Body", html=None, attachment=[], max_attachment_mb=20, timeout=1, confirm_send=True)
        with patch("mail_core.sender.ProxySMTP_SSL", return_value=RefusingSMTP()):
            with self.assertRaisesRegex(ValueError, "SMTP 拒绝一个或多个收件人") as error:
                send(self.config, args, Path.cwd())
        self.assertNotIn("secret-bcc@example.com", str(error.exception))
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            write_audit(workspace, operation="发送邮件", function="app/scripts/mail.py send", user_request="测试", status="失败", inputs={"密送人数": 1}, error=str(error.exception))
            self.assertNotIn("secret-bcc@example.com", (workspace / "logs" / "audit.jsonl").read_text(encoding="utf-8"))

    def test_download_second_imap_connection_error_is_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "manifest.json").write_text("{}", encoding="utf-8")
            (workspace / "rules").mkdir()
            (workspace / "rules" / "test.json").write_text('{"filters": {}}', encoding="utf-8")
            with patch("mail_core.reader.ProxyIMAP4_SSL", side_effect=[FakeIMAP(), OSError("private-host")]):
                with self.assertRaisesRegex(ValueError, "IMAP 网络或连接失败") as error:
                    download(self.config, workspace, "rules/test.json", workspace / "downloads", False, True, 1)
            self.assertNotIn("private-host", str(error.exception))

    def test_missing_gmail_config_and_app_password_rejection_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gmail"
            (root / "config").mkdir(parents=True)
            (root / "SKILL.md").write_text("# skill", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "无法读取文件"):
                load_config(root / "core" / "scripts" / "mail.py")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "manifest.json").write_text("{}", encoding="utf-8")
            (workspace / "rules").mkdir()
            (workspace / "rules" / "test.json").write_text('{"filters": {}}', encoding="utf-8")
            with patch("mail_core.reader.ProxyIMAP4_SSL", return_value=AppPasswordRejectingIMAP()):
                with self.assertRaisesRegex(ValueError, "Gmail IMAP 应用专用密码认证失败") as error:
                    search(self.config, workspace, "rules/test.json", 1)
            self.assertNotIn("test-app-password", str(error.exception))


if __name__ == "__main__":
    unittest.main()




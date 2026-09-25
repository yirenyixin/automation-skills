"""Offline safety tests for Tencent Exmail configuration and sending."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))

from mail_core.config import load_config  # noqa: E402
from mail_core.sender import send  # noqa: E402


def make_config_root(data: dict) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name) / "tencent-exmail"
    (root / "config").mkdir(parents=True)
    (root / "SKILL.md").write_text("# Tencent Exmail", encoding="utf-8")
    (root / "config" / "config.json").write_text(json.dumps(data), encoding="utf-8")
    return temporary, root


class ConfigAndSenderSafetyTests(unittest.TestCase):
    base_config = {
        "account": {"email": "person@example.com", "password": "local-password"},
        "smtp": {"host": "smtp.example.com", "port": 465},
        "imap": {"host": "imap.example.com", "port": 993},
    }

    def test_environment_password_overrides_local_config(self):
        temporary, root = make_config_root(self.base_config)
        self.addCleanup(temporary.cleanup)
        with patch.dict(os.environ, {"EMAIL_SKILL_PASSWORD": "environment-password"}, clear=False):
            result = load_config(root / "core" / "scripts" / "mail.py")
        self.assertEqual(result["account"]["password"], "environment-password")
        self.assertEqual(result["account"]["email"], "person@example.com")

    def test_invalid_config_sections_and_placeholder_password_are_rejected(self):
        invalid = {"account": {"email": "person@example.com", "password": "replace-with-password"}, "smtp": {}, "imap": {}}
        temporary, root = make_config_root(invalid)
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(ValueError, "配置密码"):
            load_config(root / "core" / "scripts" / "mail.py")

        missing_smtp = {"account": {"email": "person@example.com", "password": "password"}, "imap": {}}
        temporary, root = make_config_root(missing_smtp)
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(ValueError, "配置缺少 smtp 对象"):
            load_config(root / "core" / "scripts" / "mail.py")

    def test_preview_never_initializes_smtp_client(self):
        args = argparse.Namespace(
            to=["recipient@example.com"], cc=[], bcc=[], subject="Preview", text="Body", html=None,
            attachment=[], max_attachment_mb=20, timeout=1, confirm_send=False,
        )
        with patch("mail_core.sender.smtplib.SMTP_SSL") as smtp:
            result = send(self.base_config, args, Path.cwd())
        self.assertEqual(result["status"], "preview")
        smtp.assert_not_called()

    def test_header_and_recipient_injection_are_rejected_before_smtp(self):
        cases = [
            argparse.Namespace(to=["recipient@example.com\nBcc: hidden@example.com"], cc=[], bcc=[], subject="Test", text="Body", html=None, attachment=[], max_attachment_mb=20, timeout=1, confirm_send=True),
            argparse.Namespace(to=["recipient@example.com"], cc=[], bcc=[], subject="Safe\r\nBcc: hidden@example.com", text="Body", html=None, attachment=[], max_attachment_mb=20, timeout=1, confirm_send=True),
        ]
        with patch("mail_core.sender.smtplib.SMTP_SSL") as smtp:
            for args in cases:
                with self.assertRaises(ValueError):
                    send(self.base_config, args, Path.cwd())
        smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()

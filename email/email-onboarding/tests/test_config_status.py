"""Offline tests for the credential-safe onboarding status checker."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("config_status", ROOT / "scripts" / "config_status.py")
assert SPEC and SPEC.loader
config_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config_status)


class ConfigStatusTests(unittest.TestCase):
    def run_main(self, root: Path, provider: str) -> tuple[dict, str]:
        output = io.StringIO()
        with patch.object(config_status, "ROOT", root), patch.object(sys, "argv", ["config_status.py", "--provider", provider, "--request-note", "离线测试"]), contextlib.redirect_stdout(output):
            config_status.main()
        text = output.getvalue()
        return json.loads(text), text

    def test_read_json_and_nested_value_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(config_status.read_json(root / "missing.json"), (None, "文件不存在"))
            invalid = root / "invalid.json"
            invalid.write_text("not json", encoding="utf-8")
            self.assertEqual(config_status.read_json(invalid)[1], "文件不可读取或 JSON 格式无效")
            scalar = root / "scalar.json"
            scalar.write_text("[]", encoding="utf-8")
            self.assertEqual(config_status.read_json(scalar)[1], "顶层不是 JSON 对象")
        self.assertTrue(config_status.value_at({"account": {"email": "user@example.com"}}, ("account", "email")))
        self.assertFalse(config_status.value_at({"account": {"email": ""}}, ("account", "email")))

    def test_complete_qq_status_does_not_expose_authorization_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "qqmail" / "config"
            path.mkdir(parents=True)
            path.joinpath("config.json").write_text(
                json.dumps({"smtp": {"host": "smtp.qq.com"}, "imap": {"host": "imap.qq.com"}, "account": {"email": "user@qq.com", "authorization_code": "private-code"}}),
                encoding="utf-8",
            )
            result, rendered = self.run_main(root, "qqmail")
            audit = (root / "qqmail" / "logs" / "setup-audit.jsonl").read_text(encoding="utf-8")
        self.assertEqual(result["状态标记"], "【配置完成】")
        self.assertNotIn("private-code", rendered)
        self.assertNotIn("private-code", audit)
        self.assertEqual(result["连接测试"], "未执行")

    def test_missing_gmail_files_returns_user_action(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _ = self.run_main(Path(directory), "gmail")
        self.assertEqual(result["状态标记"], "【需要用户操作】")
        self.assertEqual(len(result["缺失项"]), 3)


if __name__ == "__main__":
    unittest.main()

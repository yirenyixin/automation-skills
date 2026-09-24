import importlib.util
import io
import json
import os
import pathlib
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "mysql_agent.py"
SPEC = importlib.util.spec_from_file_location("mysql_agent", MODULE)
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


class MysqlAgentTests(unittest.TestCase):
    def test_rejects_non_read_only_and_comments(self):
        for sql in ("DELETE FROM users", "SELECT 1; SELECT 2", "SELECT /* nope */ 1", "SELECT LOAD_FILE('/x')"):
            with self.assertRaises(agent.CliError):
                agent.validate_read_only_sql(sql, 20)

    def test_applies_and_bounds_limit(self):
        self.assertEqual(agent.validate_read_only_sql("SELECT id FROM orders", 20), "SELECT id FROM orders LIMIT 20")
        with self.assertRaises(agent.CliError):
            agent.validate_read_only_sql("SELECT id FROM orders LIMIT 21", 20)
        with self.assertRaises(agent.CliError):
            agent.positive_int(0, "limit", 20)

    def test_config_missing_password_is_safe(self):
        with patch.dict(os.environ, {"MYSQL_HOST": "db.example", "MYSQL_USER": "reporter"}, clear=True):
            with self.assertRaises(agent.CliError) as raised:
                agent.connection_config()
        self.assertEqual(raised.exception.code, "CONFIG_MISSING")
        self.assertNotIn("db.example", raised.exception.message)
        self.assertNotIn("reporter", raised.exception.message)

    def test_errors_are_sanitized(self):
        text = agent.sanitize_error("1045: access denied for bob@example.com using password secret-token")
        self.assertNotIn("bob@example.com", text)
        self.assertNotIn("secret-token", text)

    def test_main_emits_json_without_traceback(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.dict(os.environ, {}, clear=True):
            exit_code = agent.main(["config", "validate"])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "CONFIG_MISSING")


if __name__ == "__main__":
    unittest.main()

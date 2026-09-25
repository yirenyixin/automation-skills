import json
import pathlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = pathlib.Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mysql_workspace as workspace


class WorkspaceSafetyTests(unittest.TestCase):
    def test_medium_risk_execute_commits_and_writes_run_log(self):
        class Cursor:
            rowcount = 1
            lastrowid = 99
            def execute(self, sql, params):
                self.sql, self.params = sql, params
            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.started = self.committed = self.closed = False
            def start_transaction(self):
                self.started = True
            def cursor(self):
                return Cursor()
            def commit(self):
                self.committed = True
            def rollback(self):
                raise AssertionError("successful committed execution must not roll back")
            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "insert.sql"
            params_file = root / "params.json"
            sql_file.write_text("INSERT INTO orders (id) VALUES (%s)", encoding="utf-8")
            params_file.write_text("[99]", encoding="utf-8")
            preview, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root)))
            connection = Connection()
            connector = types.ModuleType("mysql.connector")
            connector.connect = lambda **_: connection
            package = types.ModuleType("mysql")
            package.__path__ = []
            package.connector = connector
            args = types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root), run_id=preview["run_id"], confirm=None, rollback_sql_file=None, backup_file=None, commit=True)
            with patch.dict(sys.modules, {"mysql": package, "mysql.connector": connector}), patch.dict(os.environ, {"MYSQL_HOST": "db", "MYSQL_USER": "reader", "MYSQL_PASSWORD": "secret"}, clear=True):
                result, meta = workspace.controlled_execute(args)
            self.assertTrue(connection.started)
            self.assertTrue(connection.committed)
            self.assertTrue(connection.closed)
            self.assertEqual(result["affected_rows"], 1)
            self.assertEqual(result["transaction"], "committed")
            self.assertEqual(meta["risk_level"], "medium")
            audit = (root / ".mysql-agent" / "runs" / f"{preview['run_id']}.jsonl").read_text(encoding="utf-8")
            self.assertIn('"status": "committed"', audit)
    def test_risk_classifier_matches_skill_policy(self):
        cases = {
            "SELECT * FROM orders": "low",
            "INSERT INTO orders (id) VALUES (1)": "medium",
            "UPDATE orders SET status = 'paid' WHERE id = 1": "high",
            "ALTER TABLE orders ADD COLUMN note VARCHAR(20)": "high",
            "DROP TABLE orders": "extreme",
            "TRUNCATE TABLE orders": "extreme",
            "GRANT SELECT ON app.* TO 'reader'@'%'": "extreme",
        }
        for sql, expected in cases.items():
            with self.subTest(sql=sql):
                self.assertEqual(workspace.classify(sql), expected)

    def test_workspace_init_creates_state_and_audit_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            data, _ = workspace.init_workspace(types.SimpleNamespace(workspace_dir=str(root)))
            self.assertEqual(data["root"], str(root.resolve()))
            self.assertTrue((root / ".mysql-agent" / "runs").is_dir())
            self.assertTrue((root / ".mysql-agent" / "changes").is_dir())
            self.assertTrue((root / ".mysql-agent" / "approvals").is_dir())

    def test_preview_audit_does_not_contain_raw_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            params_file = root / "params.json"
            sql_file.write_text("UPDATE users SET token = %s WHERE id = %s", encoding="utf-8")
            params_file.write_text('["very-secret-value", 7]', encoding="utf-8")
            data, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root)))
            audit = (root / ".mysql-agent" / "runs" / f"{data['run_id']}.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("very-secret-value", audit)
            self.assertIn("parameters_fingerprint", audit)

    def test_extreme_operation_requires_existing_backup_before_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            rollback_file = root / "rollback.sql"
            sql_file.write_text("DROP TABLE orders", encoding="utf-8")
            rollback_file.write_text("CREATE TABLE orders (id INT PRIMARY KEY)", encoding="utf-8")
            data, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=None, workspace_dir=str(root)))
            with self.assertRaisesRegex(ValueError, "backup-file"):
                workspace.controlled_execute(types.SimpleNamespace(sql_file=str(sql_file), params_json=None, workspace_dir=str(root), run_id=data["run_id"], confirm=data["confirmation_id"], rollback_sql_file=str(rollback_file), backup_file=None, commit=True))

    def test_expired_confirmation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            sql_file.write_text("DELETE FROM orders WHERE id = 1", encoding="utf-8")
            data, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=None, workspace_dir=str(root)))
            approval_path = root / ".mysql-agent" / "approvals" / f"{data['run_id']}.json"
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["expires_at"] = "2000-01-01T00:00:00Z"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expired"):
                workspace.controlled_execute(types.SimpleNamespace(sql_file=str(sql_file), params_json=None, workspace_dir=str(root), run_id=data["run_id"], confirm=data["confirmation_id"], rollback_sql_file=None, backup_file=None, commit=True))
    def test_high_risk_preview_archives_inputs_and_requires_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            params_file = root / "params.json"
            sql_file.write_text("UPDATE orders SET status = %s WHERE id = %s", encoding="utf-8")
            params_file.write_text('["paid", 42]', encoding="utf-8")
            data, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root)))
            self.assertEqual(data["risk_level"], "high")
            self.assertTrue(data["confirmation_required"])
            self.assertTrue((root / ".mysql-agent" / "changes" / data["run_id"] / "statement.sql").exists())
            with self.assertRaisesRegex(ValueError, "rollback-sql-file"):
                workspace.controlled_execute(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root), run_id=data["run_id"], confirm=data["confirmation_id"], rollback_sql_file=None, commit=True))

    def test_update_without_where_is_rejected_before_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            sql_file.write_text("UPDATE orders SET status = 'paid'", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "require a WHERE clause"):
                workspace.controlled_execute(types.SimpleNamespace(sql_file=str(sql_file), params_json=None, workspace_dir=str(root), run_id="unused", confirm=None, rollback_sql_file=None, backup_file=None, commit=True))
    def test_approval_cannot_be_reused_for_changed_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sql_file = root / "change.sql"
            params_file = root / "params.json"
            sql_file.write_text("DELETE FROM orders WHERE id = %s", encoding="utf-8")
            params_file.write_text('[42]', encoding="utf-8")
            data, _ = workspace.preview(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root)))
            sql_file.write_text("DELETE FROM orders WHERE id = %s AND status = 'draft'", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differ from the approved preview"):
                workspace.controlled_execute(types.SimpleNamespace(sql_file=str(sql_file), params_json=str(params_file), workspace_dir=str(root), run_id=data["run_id"], confirm=data["confirmation_id"], rollback_sql_file=None, commit=True))


if __name__ == "__main__":
    unittest.main()
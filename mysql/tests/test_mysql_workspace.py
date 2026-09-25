import json
import pathlib
import sys
import tempfile
import types
import unittest

SCRIPTS = pathlib.Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mysql_workspace as workspace


class WorkspaceSafetyTests(unittest.TestCase):
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
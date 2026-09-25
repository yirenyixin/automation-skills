import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core" / "scripts"))
from mail_core import drafts, reader


class MarkAndDraftTests(unittest.TestCase):
    def test_draft_is_local_and_attachment_must_stay_in_workspace(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            (workspace / "empty.txt").write_text("", encoding="utf-8")
            result = drafts.create_draft(workspace, SimpleNamespace(name="review", to=["recipient@example.com"], cc=[], subject="Review", text="body", html=None, attachment=["empty.txt"], overwrite=False))
            self.assertEqual("saved", result["status"])
            self.assertTrue((workspace / "drafts" / "review.json").is_file())
            with self.assertRaises(ValueError):
                drafts.create_draft(workspace, SimpleNamespace(name="outside", to=["recipient@example.com"], cc=[], subject="Review", text="", html=None, attachment=["../outside.txt"], overwrite=False))

    def test_mark_uses_explicit_uid_and_seen_flag(self):
        calls = []

        class Client:
            def select(self, mailbox, readonly):
                calls.append(("select", mailbox, readonly))
                return "OK", []
            def uid(self, *parts):
                calls.append(parts)
                return "OK", []
            def logout(self):
                calls.append(("logout",))

        with patch.object(reader, "ProxyIMAP4_SSL", return_value=Client()), patch.object(reader, "imap_login"):
            result = reader.update_read_state({"imap": {"host": "host", "port": 993}}, "INBOX", ["9", "9"], False)
        self.assertFalse(result["read"])
        self.assertIn(("store", "9", "-FLAGS.SILENT", r"(\Seen)"), calls)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; STATUS = ROOT / "scripts" / "run_status.py"; COMMAND = ROOT / "scripts" / "run_command.py"
class RunObservabilityTests(unittest.TestCase):
    def create_run(self, root, task="测试任务"):
        result = subprocess.run([sys.executable, str(STATUS), "init", "--task", task, "--root", str(root)], check=True, text=True, capture_output=True)
        return Path(result.stdout.strip())
    def test_command_error_is_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = self.create_run(temporary)
            failed = subprocess.run([sys.executable, str(COMMAND), "--run", str(run), "--phase", "失败测试", "--", sys.executable, "-c", "raise SystemExit(7)"])
            self.assertEqual(failed.returncode, 7)
            status = json.loads((run / "status.json").read_text(encoding="utf-8"))
            self.assertEqual((status["state"], status["error_kind"], status["exit_code"]), ("failed", "command_error", 7))
    def test_complete_diagnosis_is_confirmed(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = self.create_run(temporary, "完成测试")
            subprocess.run([sys.executable, str(STATUS), "update", str(run), "--state", "complete", "--phase", "交付", "--reason", "全部验证通过", "--next-action", "无"], check=True, capture_output=True)
            result = subprocess.run([sys.executable, str(STATUS), "diagnose", str(run), "--stale-seconds", "0"], check=True, text=True, capture_output=True)
            self.assertEqual(json.loads(result.stdout)["certainty"], "已确认")
    def test_stale_running_is_only_an_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = self.create_run(temporary, "中断测试")
            result = subprocess.run([sys.executable, str(STATUS), "diagnose", str(run), "--stale-seconds", "0"], check=True, text=True, capture_output=True)
            self.assertEqual(json.loads(result.stdout)["certainty"], "推断")
if __name__ == "__main__": unittest.main()

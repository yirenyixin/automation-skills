"""跨 Word、Excel、PDF 的工作区和导出安全回归测试。"""
from __future__ import annotations
import hashlib, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError(result.stderr)
    if not ok and result.returncode == 0:
        raise AssertionError("命令应当失败：" + " ".join(args))
    return result

class WorkspaceSafetyTests(unittest.TestCase):
    def test_export_is_bound_to_run_and_requires_confirmed_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "source.bin"; source.write_bytes(b"source")
            for kind in ("word", "excel", "pdf"):
                with self.subTest(kind=kind):
                    scripts = ROOT / kind / "scripts"
                    run_dir = Path(run(str(scripts / "prepare_workspace.py"), str(source), "--root", str(root / f"{kind}-runs")).stdout.strip())
                    artifact = run_dir / "result.bin"; artifact.write_bytes(b"result")
                    run(str(scripts / "record_output.py"), str(run_dir), str(root / "outside.bin"), ok=False)
                    destination = root / f"{kind}.bin"; destination.write_bytes(b"old")
                    run(str(scripts / "record_output.py"), str(run_dir), str(artifact), "--export", str(destination), ok=False)
                    expected = hashlib.sha256(b"old").hexdigest()
                    run(str(scripts / "record_output.py"), str(run_dir), str(artifact), "--export", str(destination), "--overwrite", "--expected-existing-sha256", expected)
                    self.assertEqual(destination.read_bytes(), b"result")
                    self.assertTrue(any((run_dir / "backups").iterdir()))

if __name__ == "__main__": unittest.main()

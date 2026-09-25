"""安全登记运行目录内的产物，并仅向明确目标路径导出。"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""): h.update(part)
    return h.hexdigest()

def require_within(path: Path, parent: Path, label: str) -> Path:
    resolved = path.resolve()
    try: resolved.relative_to(parent)
    except ValueError: raise ValueError(f"{label} 必须位于运行目录内：{parent}")
    return resolved

def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".export-", dir=destination.parent)
    os.close(handle)
    try:
        shutil.copy2(source, temporary); os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path); p.add_argument("artifact", type=Path)
    p.add_argument("--export", dest="destination", type=Path)
    p.add_argument("--overwrite", action="store_true", help="允许覆盖已有明确导出目标")
    p.add_argument("--expected-existing-sha256", help="覆盖前目标文件必须匹配的 SHA-256")
    a = p.parse_args(); run = a.run.resolve(); manifest_path = run / "manifest.json"
    if not manifest_path.is_file() or not run.is_dir(): p.error("运行目录必须包含 manifest.json")
    if not a.artifact.is_file(): p.error("产物文件必须存在")
    try: artifact = require_within(a.artifact, run, "artifact")
    except ValueError as exc: p.error(str(exc))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_policy") != "read-only": p.error("无效的运行清单")
    record = {"artifact": str(artifact), "sha256": digest(artifact), "recorded_at": datetime.now(timezone.utc).isoformat()}
    if a.overwrite and not a.destination: p.error("--overwrite 必须与 --export 一起使用")
    if a.destination:
        destination = a.destination.resolve()
        if destination.exists():
            if not (a.overwrite and a.expected_existing_sha256): p.error("目标已存在；如需覆盖，请同时提供 --overwrite 和 --expected-existing-sha256")
            actual = digest(destination)
            if actual.lower() != a.expected_existing_sha256.lower(): p.error("目标文件 SHA-256 与预期值不一致，拒绝覆盖")
            backup_dir = run / "backups"; backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / f"{destination.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.bak"
            shutil.copy2(destination, backup); record["backup"] = str(backup); record["replaced_sha256"] = actual
        elif a.overwrite or a.expected_existing_sha256: p.error("目标不存在，不能使用覆盖参数")
        atomic_copy(artifact, destination); record["export"] = str(destination)
    manifest.setdefault("outputs", []).append(record)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
if __name__ == "__main__": main()

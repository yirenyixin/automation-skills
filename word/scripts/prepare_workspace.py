"""Create an isolated Word run; input files are copied and never modified."""
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, nargs='+')
    p.add_argument('--root', type=Path, default=Path('.word-work'))
    a = p.parse_args(); sources = [x.resolve() for x in a.source]
    if any(not x.is_file() for x in sources): p.error('every source must be an existing file')
    a.root.resolve().mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ-'), dir=a.root.resolve()))
    inputs = run / 'inputs'; inputs.mkdir()
    records = []
    for src in sources:
        dst = inputs / src.name
        if dst.exists(): p.error(f'duplicate name: {src.name}')
        shutil.copy2(src, dst); records.append({'source': str(src), 'copy': str(dst), 'sha256': digest(src)})
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'source_policy': 'read-only', 'inputs': records, 'outputs': []}
    (run / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(run)
if __name__ == '__main__': main()



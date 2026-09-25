"""创建隔离 PDF 运行目录；源文件只复制，不修改。"""
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''): h.update(part)
    return h.hexdigest()
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('source', type=Path, nargs='+'); p.add_argument('--root', type=Path, default=Path('.pdf-work')); a = p.parse_args(); sources = [x.resolve() for x in a.source]
    if any(not x.is_file() for x in sources): p.error('每个源文件都必须存在')
    a.root.resolve().mkdir(parents=True, exist_ok=True); run = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ-'), dir=a.root.resolve())); inputs = run / 'inputs'; inputs.mkdir(); records = []
    for src in sources:
        dst = inputs / src.name
        if dst.exists(): p.error(f'重复文件名：{src.name}')
        shutil.copy2(src, dst); records.append({'source': str(src), 'copy': str(dst), 'sha256': digest(src)})
    (run / 'manifest.json').write_text(json.dumps({'created_at': datetime.now(timezone.utc).isoformat(), 'source_policy': 'read-only', 'inputs': records, 'outputs': []}, ensure_ascii=False, indent=2), encoding='utf-8'); print(run)
if __name__ == '__main__': main()


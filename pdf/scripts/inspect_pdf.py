"""提取 PDF 元数据、页数和逐页文本摘要到 JSON。"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from pypdf import PdfReader
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('source', type=Path); p.add_argument('--output', required=True, type=Path); a = p.parse_args(); reader = PdfReader(a.source)
    result = {'page_count': len(reader.pages), 'metadata': {str(k): str(v) for k, v in (reader.metadata or {}).items()}, 'pages': [{'number': i + 1, 'text': page.extract_text() or ''} for i, page in enumerate(reader.pages)]}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
if __name__ == '__main__': main()

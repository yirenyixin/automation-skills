"""检查 PDF 是否可打开、页数是否正常及是否遗留文本占位符。"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from pypdf import PdfReader
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('source', type=Path); p.add_argument('--output', required=True, type=Path); a = p.parse_args(); reader = PdfReader(a.source)
    markers = []
    for i, page in enumerate(reader.pages, 1): markers.extend({'page': i, 'marker': x} for x in re.findall(r'\{\{[^{}]+\}\}', page.extract_text() or ''))
    report = {'source': str(a.source), 'page_count': len(reader.pages), 'encrypted': reader.is_encrypted, 'unresolved_placeholders': markers, 'valid': bool(reader.pages) and not markers}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'); print(json.dumps(report, ensure_ascii=False))
if __name__ == '__main__': main()

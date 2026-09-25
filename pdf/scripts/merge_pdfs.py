"""按给定顺序合并 PDF 文件。"""
from __future__ import annotations
import argparse
from pathlib import Path
from pypdf import PdfWriter
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('source', type=Path, nargs='+'); p.add_argument('--output', required=True, type=Path); a = p.parse_args()
    if any(not x.is_file() for x in a.source): p.error('每个源文件都必须存在')
    writer = PdfWriter()
    for source in a.source: writer.append(str(source))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('wb') as f: writer.write(f)
if __name__ == '__main__': main()

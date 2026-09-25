"""使用 Poppler 将 PDF 页面渲染为 PNG。"""
from __future__ import annotations
import argparse, subprocess
from pathlib import Path
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('source', type=Path); p.add_argument('--output-prefix', required=True, type=Path); p.add_argument('--dpi', type=int, default=144); a = p.parse_args()
    a.output_prefix.parent.mkdir(parents=True, exist_ok=True); subprocess.run(['pdftoppm', '-png', '-r', str(a.dpi), str(a.source), str(a.output_prefix)], check=True)
if __name__ == '__main__': main()

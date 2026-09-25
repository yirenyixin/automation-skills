"""从受限 JSON IR 生成基础文本 PDF。"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import mm
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('input', type=Path); p.add_argument('--output', required=True, type=Path); a = p.parse_args(); data = json.loads(a.input.read_text(encoding='utf-8'))
    styles = getSampleStyleSheet(); story = []
    if data.get('title'): story += [Paragraph(str(data['title']), styles['Title']), Spacer(1, 8 * mm)]
    for block in data.get('blocks', []):
        kind, text = block.get('type'), str(block.get('text', ''))
        if kind == 'heading': story += [Paragraph(text, styles['Heading2']), Spacer(1, 3 * mm)]
        elif kind == 'paragraph': story += [Paragraph(text, styles['BodyText']), Spacer(1, 3 * mm)]
        else: p.error(f'不支持的块类型：{kind!r}')
    a.output.parent.mkdir(parents=True, exist_ok=True); doc = SimpleDocTemplate(str(a.output), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm, title=str(data.get('title', '')), author=str(data.get('author', ''))); doc.build(story)
if __name__ == '__main__': main()

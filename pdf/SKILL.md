---
name: pdf
description: 使用 Python 读取、生成、合并、渲染和校验 PDF 文件。适用于默认保护源文件、在临时工作区处理 PDF，并仅在用户明确要求时才原地覆盖的场景。
---

# PDF

使用本 skill 处理 PDF 的文本和元数据提取、程序化生成、合并、渲染与质量检查。Python 脚本负责文件操作和版式；模型只处理 JSON 中的内容、字段或明确的结构化任务。

## 源文件与版本规则

- 用户提供的 PDF 默认只读。除非用户明确给出精确路径并授权原地修改，否则不得覆盖。
- 使用已有 PDF 前，运行 `scripts/prepare_workspace.py SOURCE`，仅处理 `.pdf-work/<时间戳>/inputs/` 中的副本。
- `manifest.json` 必须记录输入路径、SHA-256、生成物哈希、导出路径和时间。渲染 PNG、检查报告与生成物放在同一运行目录。
- 仅向用户明确给出的路径导出结果。原地覆盖得到明确授权时，先在运行目录创建带时间戳的备份。

## 工作流

1. 创建隔离运行目录并复制输入。
2. 用 `inspect_pdf.py` 提取页数、元数据与文本摘要。模型只能使用该 JSON，不以文本提取结果推断精确版式。
3. 新建文档用 `generate_pdf.py` 的受限 JSON IR；仅合并现有文件时用 `merge_pdfs.py`。
4. 用 `render_pdf.py` 输出 PNG，人工或图像检查布局；再运行 `validate_pdf.py` 检查页数、文本占位符和基本打开能力。
5. 用 `record_output.py` 登记哈希，且只在目标路径明确时导出。

## 脚本路由

- `prepare_workspace.py`：创建隔离副本和版本清单。
- `inspect_pdf.py`：提取元数据、页数和每页文本摘要。
- `generate_pdf.py`：由受限 JSON IR 生成基础文本 PDF。
- `merge_pdfs.py`：按给定顺序合并 PDF 副本。
- `render_pdf.py`：通过 Poppler 将页面渲染为 PNG。
- `validate_pdf.py`：检查文件、页数和未替换占位符。
- `record_output.py`：记录哈希并导出到明确路径。

创建内容前阅读 [数据协议](references/data-contracts.md)。处理扫描件、签名、加密文件、AcroForm、复杂排版或中文字体时阅读 [限制](references/limitations.md)。

## 安全导出

`record_output.py` 只接受位于当前运行目录中的产物。若导出目标已存在，默认拒绝；覆盖时必须同时提供 `--overwrite` 与该目标的 `--expected-existing-sha256`，脚本会先在运行目录的 `backups/` 中保存备份。该哈希不匹配时不会覆盖。

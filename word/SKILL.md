---
name: word
description: 使用确定性的 Python 工具读取、生成、填充和校验 Word DOCX 文档。适用于默认保护源文件、仅在用户明确要求时才原地覆盖的 Word 操作。
---

# Word

使用本 skill 处理 `.docx` 的读取、模板填充、生成、提取和校验。Python 脚本负责文档结构和格式；模型仅可提供符合既定 JSON 协议的文本或数据，不得推断或重建布局。

## 源文件与版本规则

- 用户提供的源文件默认只读；仅当用户明确指定文件并要求原地修改时才允许覆盖。
- 基于源文件操作前，运行 `scripts/prepare_workspace.py SOURCE`。只能编辑其在 `.word-work/<运行目录>/inputs/` 中的副本。
- 运行清单会记录源路径、SHA-256、副本、生成物和时间；报告、渲染结果也必须放入该运行目录。
- 仅向明确的目标路径导出。不得静默覆盖源文件；获得覆盖授权时须先在运行目录创建备份。

## 工作流

1. 创建临时运行目录。
2. 需要分析时使用 `inspect_docx.py` 提取 JSON，模型仅接收该 JSON。
3. 固定模板使用 `fill_template.py`；新文档使用 `generate_docx.py` 和 JSON IR。
4. 运行 `validate_docx.py`。版式重要时，使用 LibreOffice 渲染 PDF 并检查结果。
5. 使用 `record_output.py` 计算哈希、更新 `manifest.json`，并只向明确目标导出；交付生成物、清单和校验报告，保留原文件不变。

## 脚本路由

- `prepare_workspace.py`：隔离输入并写入清单。
- `inspect_docx.py`：将 DOCX 转为确定性的 JSON。
- `fill_template.py`：在复制的模板中替换标量 `{{field}}`；占位符必须位于单一 run，避免破坏格式。
- `generate_docx.py`：从受限 JSON 生成标题、段落和表格。
- `validate_docx.py`：报告未替换字段和基础问题。
- `record_output.py`：登记产物哈希，并向明确目标安全导出。

生成模板数据或文档 IR 前阅读 [数据协议](references/data-contracts.md)。处理修订、批注、域、嵌入对象或启用宏的文件前阅读 [限制说明](references/limitations.md)。

## 安全导出

`record_output.py` 只接受位于当前运行目录中的产物。若导出目标已存在，默认拒绝；覆盖时必须同时提供 `--overwrite` 与目标的 `--expected-existing-sha256`。脚本会先在运行目录的 `backups/` 中保存备份；哈希不匹配时不会覆盖。

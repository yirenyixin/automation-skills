---
name: excel
description: 使用 Python 读取、生成、填充和校验 Excel XLSX 工作簿。适用于默认保护源文件、在临时工作区完成数据、公式和格式操作，并仅在用户明确要求时才原地覆盖的场景。
---

# Excel

使用本 skill 处理 `.xlsx` 文件的读取、模板填充、公式生成、格式化和校验。Python 脚本负责工作簿结构、单元格类型、公式和格式；模型只处理明确 schema 内的表格数据、文案或计算规则。

## 源文件与版本规则

- 用户提供的工作簿默认只读。除非用户明确给出文件路径并授权原地修改，否则不得覆盖。
- 操作已有工作簿前，运行 `scripts/prepare_workspace.py SOURCE`，仅处理返回的 `.excel-work/<时间戳>/inputs/` 副本。
- 每次运行的 `manifest.json` 必须记录输入路径、SHA-256、生成物哈希、导出路径和时间。报告、渲染物和日志与该清单放在同一运行目录。
- 只有给出明确导出路径时才复制结果；明确要求覆盖源文件时，先在运行目录建立带时间戳的备份。

## 工作流

1. 创建临时运行目录并复制输入。
2. 需要分析时，用 `inspect_xlsx.py` 生成 JSON；模型仅接触该 JSON，不直接猜测表格结构或公式。
3. 固定表格用 `fill_template.py` 填充 `{{字段}}`；新工作簿用 `generate_xlsx.py` 从 JSON IR 生成。
4. 使用 `validate_xlsx.py` 检查未替换字段、错误值和基本结构。涉及复杂公式或可视化时，在目标 Excel 引擎中复算并人工检查。
5. 用 `record_output.py` 登记产物哈希，并仅导出到用户指定位置。

## 脚本路由

- `prepare_workspace.py`：创建隔离副本和版本清单。
- `inspect_xlsx.py`：提取工作表、单元格值、公式和格式摘要。
- `fill_template.py`：替换标量 `{{字段}}`，保留工作簿的其他内容。
- `generate_xlsx.py`：从受限 JSON IR 创建工作表、原生数据类型、公式和基础格式。
- `validate_xlsx.py`：检查占位符、已保存的公式错误值和工作表结构。
- `record_output.py`：记录哈希并向明确目标路径导出。

生成 IR 前阅读 [数据协议](references/data-contracts.md)。处理宏、透视表、图表、外部连接、复杂条件格式或原生 Excel 复算时阅读 [限制](references/limitations.md)。

## 安全导出

`record_output.py` 只接受位于当前运行目录中的产物。若导出目标已存在，默认拒绝；覆盖时必须同时提供 `--overwrite` 与该目标的 `--expected-existing-sha256`，脚本会先在运行目录的 `backups/` 中保存备份。该哈希不匹配时不会覆盖。

# 附件内容读取与临时空间

仅在用户明确要求读取已匹配邮件的附件内容时使用本说明。附件下载、解压、脚本生成和模型分析都属于本次任务工作区内的处理；不得改变邮件状态，不得把附件复制到其他服务商工作区。

## 读取顺序

1. 先以 `download` 预览附件集合，取得用户对准确邮件、附件和目标临时目录的确认。
2. 使用 `--confirm-download --output downloads/attachments-reading/<读取名>` 下载。下载记录仍写入 `outputs/download-record.json`。
3. 在当前项目与会话可用的 skills 中寻找匹配类型的读取能力，并先读取其 `SKILL.md`。优先级是：Excel、CSV 等表格使用 `spreadsheets`；PDF 使用 `pdf`；Word 文档使用 `documents`。
4. 压缩包先只列出成员名称、压缩大小和解压后大小；拒绝绝对路径、`..` 路径、加密包和可疑的解压比例。用户指定需要的成员后，再仅解压该成员到同一临时目录。
5. 没有合适 skill 时，在 `downloads/attachments-reading/<读取名>/tools/` 创建只读的最小脚本；脚本只处理本次已下载文件。纯文本或无法可靠解析的内容可使用模型自身能力读取。

## 输出标注

对每个附件或汇总段落写明以下三类之一：

- `读取方式：引用 skill：spreadsheets`（或实际 skill 名称）
- `读取方式：本次生成脚本：downloads/attachments-reading/<读取名>/tools/<脚本名>`
- `读取方式：模型自身识别`

说明文件名、来源邮件 UID 和处理范围；不要把完整敏感附件内容写入审计日志。结论后必须提醒用户审核，特别是数字、日期、公式、扫描件 OCR 结果、压缩包成员和可能包含恶意内容的附件。

## 容量检查

每次 `mail.py` 命令启动时都会计算整个 `workspaces/` 的占用，并读取 `config/workspace-policy.json` 的 `workspace_size_limit_mb`；默认值为 500 MB。达到或超过阈值时，除 `check-storage` 外的命令会在连接邮箱、下载或写入产物前停止；不会自动删除任何内容。优先建议清理已确认不再需要的 `downloads/`、`outputs/`、`logs/` 与 `drafts/` 中的最大文件，保留 `app/`、`rules/` 与 `manifest.json` 以维持可追溯性。

只有用户明确授权时，才可删除所列的准确路径或修改阈值配置；报告删除后的新占用。

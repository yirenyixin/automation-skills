---
name: gmail
description: "当用户明确要求通过 Gmail、Google Mail 或 @gmail.com 邮箱发送、搜索、读取邮件或下载附件时使用。使用独立工作区中的 Python SMTP/IMAP 脚本和 OAuth 2.0；不使用网页登录密码，也不用于腾讯企业邮箱、QQ 邮箱或普通邮件文案。"
---

# Gmail 邮件操作

仅处理已完成本地 OAuth 配置的 Gmail。本目录的配置、核心代码、工作区、日志与令牌必须与腾讯企业邮箱、QQ 邮箱完全隔离。

1. 先在本目录运行 `python scripts/create_workspace.py <任务名> --description "<脱敏范围>"`，后续只在 `workspaces/<任务名>/` 运行 `app/scripts/mail.py`。执行前阅读 [agent-workflow.md](references/agent-workflow.md)，规则使用 [rule-schema.md](references/rule-schema.md)。
2. `send` 与 `download` 必须先预览。只有用户针对准确收件人、主题、正文、附件集合和目标路径再次明确确认后，才能使用确认参数执行。
3. 每个命令先检查全部 `workspaces/` 占用，默认阈值 500 MB。超限时除 `check-storage` 外停止，不加载 OAuth 配置、不连接邮箱、不写入结果，也不自动删除。
4. 所有命令都传入脱敏 `--request-note`。不得在参数、日志、规则、输出、工作区或回复中泄露 client secret、access token、refresh token、BCC 或完整附件内容。

## OAuth 与用户交互

- 使用本地、被忽略的 `config/oauth-client.json`、`config/account.json` 和 `config/token.json`；绝不接受或保存 Gmail 网页登录密码。
- `python scripts/oauth_authorize.py` 显示本地浏览器授权链接并等待用户完成 Google OAuth。浏览器登录、同意、CAPTCHA 或 OTP 均需用户完成；智能体必须暂停，不能绕过。
- 脚本只在用户明确启动 OAuth 授权时保存令牌；保存后不会自动读取、搜索或发送邮件。后续具体邮件操作才会按需刷新令牌并连接。
- 用户明确要求保存 OAuth 文件或令牌时，只更新对应被忽略文件并仅报告已更新，不回显或复制秘密。

## 内容与异常

`search`、`read`、附件下载、审计、容量检查与腾讯企业邮箱的安全模式一致。附件内容处理遵循 [attachment-reading.md](references/attachment-reading.md)，最终标注读取方式并提示用户审核。配置、OAuth、网络、规则或路径失败时停止并返回脱敏错误类别；不自动重试、不扩大搜索范围或切换服务商。

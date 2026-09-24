---
name: qqmail
description: "当用户明确要求通过 QQ 邮箱或 @qq.com、@foxmail.com 邮箱发送、搜索、读取邮件或下载附件时使用。使用独立工作区中的 Python SMTP/IMAP 脚本和 QQ 客户端授权码；不用于腾讯企业邮箱、Gmail 或普通邮件文案。"
---

# QQ 邮箱邮件操作

仅处理已配置的 QQ 邮箱。QQ 邮箱的配置、核心代码、工作区、日志与凭据必须保持在本目录；不得读取或使用腾讯企业邮箱、Gmail 的任何文件或凭据。

1. 先在本目录运行 `python scripts/create_workspace.py <任务名> --description "<脱敏范围>"`，后续只在 `workspaces/<任务名>/` 运行 `app/scripts/mail.py`。执行前阅读 [agent-workflow.md](references/agent-workflow.md)，规则使用 [rule-schema.md](references/rule-schema.md)。
2. `send` 与 `download` 必须先预览。只有用户针对准确收件人、主题、正文、附件集合和目标路径再次明确确认后，才能使用确认参数执行。
3. 每个命令先检查全部 `workspaces/` 占用，默认阈值由 `config/workspace-policy.json` 的 500 MB 控制。超限时除 `check-storage` 外停止，不连接邮箱、不写入结果、不自动删除。
4. 每次命令在子命令前传入脱敏的 `--request-note`。不得将授权码、密码、密送地址、完整正文或附件内容写入参数、规则、输出或审计日志。

## 认证与授权

- 只使用 `config/config.json` 的完整 QQ/foxmail 地址和 `account.authorization_code`；只能使用 QQ 邮箱客户端授权码，绝不使用网页登录密码。
- 用户明确要求保存其自行提供的账号和授权码时，只更新被忽略的 `config/config.json`；写入后仅报告配置已更新，绝不回显或复制秘密。保存后不得自动连接。
- CAPTCHA、短信/OTP 验证或网页登录需要用户交互时，暂停等待；不得绕过、模拟或索取验证码。

## 内容与异常

`search` 返回邮件头和附件元数据；`read` 可按需读取正文但不改变已读状态。附件内容处理遵循 [attachment-reading.md](references/attachment-reading.md)，并标注读取 skill、临时脚本或模型识别方式，最后提示用户审核。配置、认证、网络、规则或路径失败均停止；不自动重试、不扩大范围、不切换服务商，且不得记录服务器原始错误或 BCC 地址。

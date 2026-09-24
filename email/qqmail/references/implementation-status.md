# QQ 邮箱实现与配置状态

本 skill 已实现独立的 SMTP/IMAP 发送、搜索、只读正文读取、附件预览与下载、审计日志、工作区容量检查和本地离线测试。实际执行文件位于任务工作区的 `app/scripts/mail.py`。

1. 在 QQ 邮箱网页版“设置”→“账号与安全”→“安全设置”中开启 **IMAP/SMTP 服务**，完成验证并生成客户端授权码。
2. 将 `config/config.example.json` 复制为被忽略的 `config/config.json`，填写完整 QQ/foxmail 地址和授权码；服务器为 `imap.qq.com:993` 与 `smtp.qq.com:465`，均使用 SSL。
3. 运行 `python ..\email-onboarding\scripts\config_status.py --provider qqmail` 检查字段状态；该检查不会连接邮箱。

不得使用 QQ 网页登录密码。保存授权码后，等待用户后续明确的具体邮件操作。详细命令和确认边界见 [agent-workflow.md](agent-workflow.md)。

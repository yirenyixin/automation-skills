# Gmail 实现与配置状态

本 skill 已实现独立的 Gmail OAuth 2.0、XOAUTH2 SMTP/IMAP 发送、搜索、只读正文读取、附件预览与下载、审计日志、工作区容量检查和本地离线测试。

1. 在 Google Cloud 创建 OAuth 桌面应用客户端，将下载内容保存为被忽略的 `config/oauth-client.json`；模板为 `config/oauth-client.example.json`。
2. 将 `config/account.example.json` 复制为被忽略的 `config/account.json`，只填写 Gmail 地址。
3. 用户明确启动浏览器授权后，运行 `python scripts/oauth_authorize.py`；用户在浏览器完成登录、同意和必要的 CAPTCHA/OTP 后，脚本写入被忽略的 `config/token.json`，不会显示令牌。
4. 运行 `python ..\email-onboarding\scripts\config_status.py --provider gmail` 检查本地文件状态；该检查不连接邮箱。

不得使用或保存 Gmail 网页登录密码。保存 OAuth 文件或令牌后不自动连接，等待用户后续明确的具体邮件操作。详细命令和确认边界见 [agent-workflow.md](agent-workflow.md)。

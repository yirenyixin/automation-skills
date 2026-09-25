# 自动化 Skills

这是一个面向 Codex 的中文自动化 skill 集合，覆盖浏览器、邮件、MySQL 与 Office/PDF 文档处理。每个 skill 均将稳定的操作逻辑、配置说明和测试放在独立目录中，任务产生的数据不进入仓库。

项目仍在修改和验证中。

## 目录

| 目录 | 用途 | 入口 |
| --- | --- | --- |
| [`browser/browser-automation`](browser/browser-automation) | 基于 Edge 或 Chrome MCP 的浏览、表单操作、数据导出与工作流执行 | [`SKILL.md`](browser/browser-automation/SKILL.md) |
| [`email`](email) | Gmail、QQ 邮箱与腾讯企业邮箱的发送、搜索、读取和附件处理 | 各子目录的 `SKILL.md` |
| [mysql](mysql) | MySQL 结构发现、查询与受控变更 | [SKILL.md](mysql/SKILL.md) |
| [word](word) | Word .docx 的生成、检查、模板填充与工作区管理 | [SKILL.md](word/SKILL.md) |
| [pdf](pdf) | PDF 的生成、检查、渲染、合并与工作区管理 | [SKILL.md](pdf/SKILL.md) |
| [xcel](excel) | Excel .xlsx 的生成、检查、模板填充与工作区管理 | [SKILL.md](excel/SKILL.md) |

## 安全边界

- **不提交真实凭据。** 邮箱账号、密码、客户端授权码、OAuth client secret、访问令牌和刷新令牌只能保存在本地配置或环境变量中。
- **只提交示例配置。** 可提交 `*.example.json`，其中敏感字段必须使用 `replace-with-...` 等提示值；不要提交实际的 `config.json`、`account.json`、`oauth-client.json` 或 `token.json`。
- **不提交运行数据。** 任务工作区、邮件内容、附件、日志、导出结果、缓存与 Python 字节码均由根目录 `.gitignore` 排除。
- **浏览器验证由用户完成。** skill 不会破解或绕过 CAPTCHA、OTP 或其他人机验证；发送、发布、支付、删除和重要表单提交须在最终步骤取得用户确认。
- **MySQL 默认只读。** `mysql/scripts/mysql_agent.py` 拒绝写操作、多语句和无界查询；生产连接与权限配置仍须由用户明确授权。

## 本地配置

请从示例文件开始创建仅存在于本机的配置文件，并填入自己的账户信息：

```text
email/tencent-exmail/config/config.example.json
email/qqmail/config/config.example.json
email/gmail/config/account.example.json
email/gmail/config/oauth-client.example.json
```

MySQL 连接信息通过 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD` 和可选的 `MYSQL_DATABASE` 环境变量提供。不要把任何凭据写入命令历史、规则、日志、测试结果或提交信息。

## 验证

各 skill 附带本地测试；运行前请安装相应运行时和依赖。示例：

```powershell
# 浏览器自动化
node browser/browser-automation/tests/run-tests.mjs

# 邮件 skill（分别在对应目录执行）
python email/gmail/tests/test_local.py
python email/qqmail/tests/test_local.py
python email/tencent-exmail/tests/test_local.py

# MySQL 只读 skill
pip install -r mysql/requirements.txt
python mysql/tests/test_mysql_agent.py
```

详细的操作步骤、能力范围和限制请以每个目录的 `SKILL.md` 与 `references/` 文档为准。

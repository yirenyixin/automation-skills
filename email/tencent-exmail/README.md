# 腾讯企业邮箱工作区 Skill

通过 Python 标准库使用腾讯企业邮箱的 SMTP 与 IMAP 服务。稳定代码保留在 `core/`；每项用户需求创建独立工作区，在其派生版本中修改和执行，避免临时需求影响基础代码。

## 能力

- 发送邮件：预览、收件人/附件校验、显式确认投递、唯一 `Message-ID`。
- 查看邮件：按规则搜索、输出 JSON、读取正文摘要或完整纯文本正文。
- 附件归档：先预览后下载，防止路径穿越与重复下载，并记录来源邮件与本地路径。
- 自动化：按规则检查新匹配邮件，不会自动发送、下载或修改邮件。
- 安全：密码仅保存在本地配置或环境变量；审计日志不记录密码与密送人地址。

## 目录

```text
tencent-exmail/
├─ config/                   # 本地凭据与配置
├─ core/                     # 稳定基础代码，版本见 core/VERSION
├─ scripts/create_workspace.py
├─ config/workspace-policy.json # 全部任务工作区的容量阈值，默认 500 MB
├─ workspaces/               # 每次任务的独立工作版本
├─ references/rule-schema.md # 规则与任务文件格式
└─ tests/                    # 不连接真实邮箱的本地模拟测试
```

## 首次配置

1. 将 `config/config.example.json` 复制为 `config/config.json`。
2. 填写完整企业邮箱地址和密码；如果启用安全登录，请使用客户端专用密码。
3. 确认管理员和账号已启用 SMTP/IMAP 客户端访问权限。

默认服务：SMTP `smtp.exmail.qq.com:465`、IMAP `imap.exmail.qq.com:993`，均使用 SSL。真实配置被 `.gitignore` 排除。也可以设置 `EMAIL_SKILL_PASSWORD` 环境变量覆盖配置文件中的密码。

## 创建工作区

```powershell
cd E:\workspace\SkillTest\email\tencent-exmail
python scripts/create_workspace.py finance-review --description "筛选财务未读邮件"
cd workspaces\finance-review
python app\scripts\mail.py --help
```

工作区包含 `app/`（基础代码派生版本）、`rules/`、`drafts/`、`outputs/`、`downloads/` 和 `logs/`。一次性修改只改该工作区；确认可复用并通过测试后，才升级 `core/` 的版本。

每次执行邮件命令都会检查所有 `workspaces/` 的总占用。默认阈值为 500 MB，可在 `config/workspace-policy.json` 的 `workspace_size_limit_mb` 调整。超限时，除 `check-storage` 外的命令都会停止，不加载凭据、不连接邮箱也不写入产物；脚本仅列出 `downloads/`、`outputs/`、`logs/`、`drafts/` 中可优先清理的最大文件，绝不自动删除。可用 `python app\scripts\mail.py check-storage` 进行只读检查。

## 发送邮件

默认只预览，不会投递：

```powershell
python app\scripts\mail.py send --to recipient@example.com --subject "测试" --text "这是一封测试邮件。"
```

确认收件人、主题、正文和附件后，才允许投递：

```powershell
python app\scripts\mail.py send --to recipient@example.com --subject "测试" --text "这是一封测试邮件。" --confirm-send
```

`--to`、`--cc`、`--bcc` 和 `--attachment` 可重复使用。单个附件默认上限为 20 MB，可通过 `--max-attachment-mb` 调整。

## 查阅邮件

在工作区创建规则文件，例如 `rules/finance-unread.json`：

```json
{
  "mailbox": "INBOX",
  "filters": {
    "from": "finance@example.com",
    "subject_contains": "发票",
    "unread": true,
    "has_attachment": true,
    "attachment_extension": ".pdf"
  }
}
```

搜索结果默认写入 `outputs/mail-results.json`：

```powershell
python app\scripts\mail.py search --rule rules/finance-unread.json
python app\scripts\mail.py read --rule rules/finance-unread.json
python app\scripts\mail.py read --rule rules/finance-unread.json --uid 123 --full-body
```

AI 可基于用户明确允许的 JSON 结果提取待办、日期、联系人、金额或风险项；不得读取超出筛选范围的邮件，也不接触凭据。

## 下载附件

先查看将下载哪些附件：

```powershell
python app\scripts\mail.py download --rule rules/finance-unread.json --limit 200
```

确认后下载到当前工作区的 `downloads/`：

```powershell
python app\scripts\mail.py download --rule rules/finance-unread.json --limit 200 --confirm-download
```

下载到工作区外的用户指定目录必须同时使用 `--allow-external-output`。`--limit` 必须为正整数，预览会说明候选总数、实际处理数及是否截断。每次操作会生成 `outputs/download-record.json`，其中包含来源 UID、附件名和保存路径。

如需阅读附件内容，下载到 `downloads/attachments-reading/<读取名>/`。优先用当前可用的文件读取 skill：表格用 `spreadsheets`、PDF 用 `pdf`、Word 用 `documents`；若没有匹配 skill，才在该目录创建只读脚本或使用模型自身识别。结果会明确标注读取方式，涉及金额、日期、公式、扫描件或压缩包时请人工审核。

## 自动化

创建任务文件，例如 `rules/finance-job.json`：

```json
{
  "rule": "rules/finance-unread.json",
  "limit": 50,
  "state_file": "outputs/finance-state.json"
}
```

执行一次：

```powershell
python app\scripts\mail.py run-job --job rules/finance-job.json
```

可用 Windows 任务计划程序定时运行该命令。它只报告新匹配邮件，不会自动下载、发送或更改邮件状态。

## 测试

测试使用本地模拟 SMTP/IMAP，不访问真实服务器：

```powershell
cd E:\workspace\SkillTest\email\tencent-exmail
python tests\test_local.py
```

规则字段详见 [references/rule-schema.md](references/rule-schema.md)，AI 调用边界详见 [SKILL.md](SKILL.md)。

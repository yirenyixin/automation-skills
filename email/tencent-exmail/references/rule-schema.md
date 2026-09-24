# 规则文件

在工作区创建 `rules/<名称>.json`。示例：

```json
{
  "mailbox": "INBOX",
  "filters": {
    "from": "finance@example.com",
    "subject_contains": "发票",
    "since": "01-Sep-2026",
    "unread": true,
    "has_attachment": true,
    "attachment_extension": ".pdf"
  }
}
```

`from`、`to`、`subject`、`since`、`before` 和 `unread` 会用于 IMAP 初步搜索；`*_contains`、附件条件会在本地复核。日期使用 IMAP 格式 `DD-Mon-YYYY`。规则不包含密码，也不应包含不必要的邮件正文。

# 自动化任务

```json
{
  "rule": "rules/finance-unread.json",
  "limit": 50,
  "state_file": "outputs/finance-state.json"
}
```

操作系统可定时执行 `python app/scripts/mail.py run-job --job rules/finance-job.json`。它只保存并报告新匹配 UID，不会发送、下载或修改邮件。

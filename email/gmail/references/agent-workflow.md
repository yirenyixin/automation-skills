# Agent 命令工作流

以下命令均在 `workspaces/<任务名>/` 中执行。先从 skill 根目录创建工作区：

```powershell
python scripts/create_workspace.py <任务名> --description "<用户需求范围>"
```

任务名使用小写字母、数字和连字符。不得在 `manifest.json` 中写入密码、真实邮件正文或与本次任务无关的用户数据。

每次执行 `app/scripts/mail.py` 时，在子命令前添加 `--request-note "<脱敏的用户请求摘要>"`。例如：`python app/scripts/mail.py --request-note "读取 UID 3229 的完整正文，不改变状态" read ...`。该摘要会写入 `logs/audit.jsonl`；不得填入密码、密送地址或完整邮件正文。

每次命令会先检查 `工作区容量检查`：检测范围是本 skill 下全部 `workspaces/`，默认阈值来自 `config/workspace-policy.json` 的 `workspace_size_limit_mb`（500 MB）。状态为“超出阈值”时，除 `check-storage` 外的命令会在加载凭据、连接邮箱和写入产物前停止；不得自动删除或忽略警告。报告结果中的 `可优先清理` 路径，请用户明确选择删除文件，或明确授权修改阈值。

只检查容量且不连接邮箱、不加载配置、不写入文件时，执行：

```powershell
python app/scripts/mail.py check-storage
```

## 发送邮件

必填输入：至少一个收件人、主题和纯文本正文。缺少任一项时先询问用户。若用户指定附件，在预览前确认附件存在。

先执行预览：

```powershell
python app/scripts/mail.py --request-note "预览发送测试邮件" send --to recipient@example.com --subject "<主题>" --text "<正文>"
```

返回 `status: preview` 表示尚未发送。取得用户对准确收件人、主题、正文和附件列表的当前明确授权后，才可投递：

```powershell
python app/scripts/mail.py --request-note "用户确认发送测试邮件" send --to recipient@example.com --subject "<主题>" --text "<正文>" --confirm-send
```

可按需重复使用 `--to`、`--cc`、`--bcc` 和 `--attachment`。`submitted` 仅表示 SMTP 服务器已接受投递请求，不代表邮件已送达收件箱。结果不明确的失败不能自动重试，以免重复发送。

## 搜索与查看邮件

必填输入：用户明确批准的搜索范围。需求不完整时，至少询问以下信息中的必要项：邮箱目录、发件人/收件人、主题关键词、日期范围、未读状态、附件条件和期望的总结类型。

依据 [rule-schema.md](rule-schema.md) 创建 `rules/<名称>.json`，然后执行：

```powershell
python app/scripts/mail.py search --rule rules/<名称>.json
python app/scripts/mail.py read --rule rules/<名称>.json
```

`search` 返回邮件头和附件元数据；`read` 额外返回简短正文预览。`read --uid <uid> --full-body` 会返回每个非附件正文 MIME 部分：纯文本、HTML 源码及其可读文本转换、其他文本类型，以及内联二进制部分的元数据。附件本身仍须通过下载流程获取。结果写入 `outputs/mail-results.json`。

有返回结果时，仅总结用户允许的字段。若用户要求提取待办、联系人、日期、金额或风险，每项重要结论都应标明来源 UID；不确定内容必须明确标注，不能补全或猜测缺失事实。

## 标记已读或未读

这是会修改远程邮箱状态的操作。执行前必须取得用户对**准确邮箱目录、UID 列表和目标状态**的当前明确授权；不得将“查看邮件”或“搜索未读”视为标记授权。UID 来自已批准范围内的搜索或读取结果。

```powershell
python app/scripts/mail.py --request-note "将指定邮件标为已读" mark --mailbox INBOX --uid <UID> --read
python app/scripts/mail.py --request-note "将指定邮件标为未读" mark --mailbox INBOX --uid <UID> --unread
```

可重复传入 `--uid`。命令以 UID 精确设置或清除 IMAP `\\Seen` 标记；成功仅表示服务器接受了状态更新。网页端若按会话聚合，仍可能因同一会话的其他未读邮件显示加粗，不能据此推断该 UID 的更新失败。

## 保存草稿

`draft` 只在当前工作区的 `drafts/` 保存 JSON 草稿，不发送邮件，也不写入远程“草稿箱”。必填输入：至少一个收件人、主题和草稿名称。附件必须已经位于当前工作区。已有同名草稿默认不覆盖。

```powershell
python app/scripts/mail.py --request-note "保存待审核邮件草稿" draft --name <名称> --to recipient@example.com --subject "<主题>" --text "<正文>"
```

可按需使用 `--cc`、`--html` 和 `--attachment`；只有用户明确要求覆盖同名草稿时才可传 `--overwrite`。草稿内容属于本地任务数据，报告时仅给出相对路径与摘要，不回显完整正文或密送信息。
## 下载附件

必填输入：用户批准的规则和目标目录。先执行预览：

```powershell
python app/scripts/mail.py download --rule rules/<名称>.json --limit 200
```

用户确认预览出的附件集合和目标目录后，下载到默认工作区目录：

```powershell
python app/scripts/mail.py download --rule rules/<名称>.json --limit 200 --confirm-download
```

`--limit` 必须是正整数；预览结果中的 `选择范围` 会报告服务器候选总数、实际处理数、上限和是否截断。不得隐瞒截断，也不得在用户未确认预览出的准确集合时下载。若用户指定工作区外位置，使用其精确绝对路径，并附加 `--allow-external-output`。脚本会跳过已有同名目标，不会覆盖。将 `outputs/download-record.json` 作为可追溯记录报告给用户。

## 读取附件内容

用户要求查看附件内容时，先完成下载预览与确认；目标目录使用 `downloads/attachments-reading/<读取名>`。下载后先查找本项目和当前会话是否有适合的读取 skill，并读取其 `SKILL.md`；表格优先 `spreadsheets`，PDF 优先 `pdf`，Word 优先 `documents`。没有可用 skill 时，才在该临时目录创建只读最小脚本，或使用模型自身能力读取。

压缩包先列成员，不自动解压；拒绝路径穿越、加密包和异常解压体积，仅在用户指定成员后解压该成员。每项结果必须写明 `读取方式：引用 skill：<名称>`、`读取方式：本次生成脚本：<路径>` 或 `读取方式：模型自身识别`，并提醒用户审核。

## 监控新匹配邮件

按 [rule-schema.md](rule-schema.md) 创建任务 JSON，然后执行：

```powershell
python app/scripts/mail.py run-job --job rules/<任务名>.json
```

该命令只记录已见 UID 并报告新匹配结果；它不会发送、下载、删除、标记邮件或创建计划任务。用户要求周期执行时，使用运行环境允许的调度/自动化机制，并保留原规则、工作区和通知偏好。未被要求时，不得把一次性搜索变成循环任务。

## 错误映射

| 脚本结果 | Agent 处理方式 |
| --- | --- |
| 本地配置缺失或无效 | 停止执行，请用户更新本地配置；绝不索取或打印密码。 |
| SMTP/IMAP 认证、权限或网络失败 | 停止执行；说明错误类别，建议检查本地密码/客户端专用密码、服务权限或网络。不得自动重试。 |
| 规则 JSON 或路径错误 | 保持原任务范围；仅修改已命名的任务规则，或询问用户缺失的筛选条件。 |
| 零匹配结果 | 报告零结果及使用的准确规则；不得自动扩大范围。 |
| 预览结果 | 明确说明尚未发生外部操作；启用确认标志前请求或核实授权。 |
| 容量超出阈值 | 仅报告容量检查和可清理路径；不得连接邮箱、写入产物或自动删除。 |
| 附件路径冲突 | 报告被跳过的文件；不得删除或覆盖。 |

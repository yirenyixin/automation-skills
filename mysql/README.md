# MySQL 只读查询 Skill

该 Skill 通过 `scripts/mysql_agent.py` 提供由脚本强制约束的 MySQL 查询能力。它适用于连通性验证、库表结构发现、参数化查询、执行计划检查和有限结果导出；不提供写入、建表、授权或事务命令。

所有命令都从 **`mysql/` 目录**运行，并向标准输出返回一行 JSON。调用方应读取 JSON 字段，而不是依赖终端错误文本。

## 快速开始

```powershell
cd .\mysql
python -m pip install -r requirements.txt

# 在当前 PowerShell 会话中设置连接信息；请勿把密码写进脚本或提交到版本库
$env:MYSQL_HOST = "db.example.internal"
$env:MYSQL_USER = "report_reader"
$env:MYSQL_PASSWORD = "<password>"
$env:MYSQL_DATABASE = "app"       # 可选：省略后在命令中使用 --database

python scripts/mysql_agent.py config validate
python scripts/mysql_agent.py ping
```

`config validate` 仅校验配置并输出脱敏摘要，不会连接数据库；`ping` 会执行一条只读查询以验证连接。

## 安装

建议在独立的 Python 虚拟环境中安装依赖：

```powershell
cd mysql
python -m pip install -r requirements.txt
```

## 配置

通过环境变量提供连接信息，不要将密码写进 SQL、参数文件、命令历史或版本控制。

| 变量 | 是否必需 | 默认值 |
| --- | --- | --- |
| `MYSQL_HOST` | 是 | — |
| `MYSQL_PORT` | 否 | `3306` |
| `MYSQL_USER` | 是 | — |
| `MYSQL_PASSWORD` | 是 | — |
| `MYSQL_DATABASE` | 否 | — |
| `MYSQL_CONNECT_TIMEOUT` | 否 | `5` 秒 |
| `MYSQL_READ_TIMEOUT` | 否 | `15` 秒 |
| `MYSQL_MAX_ROWS` | 否 | `200`（最大 `1000`） |
| `MYSQL_MAX_EXPORT_BYTES` | 否 | `10485760` 字节 |

先验证配置，再测试连通性：

```powershell
python scripts/mysql_agent.py config validate
python scripts/mysql_agent.py ping
```

PowerShell 中可用 `Remove-Item Env:MYSQL_PASSWORD` 在当前会话结束前清除密码变量。生产环境推荐由 CI 密钥库、受控运行环境或安全的凭据注入机制设置这些变量。

## 常用命令

发现可访问的库表和表结构：

```powershell
python scripts/mysql_agent.py list-databases
python scripts/mysql_agent.py list-tables --database app
python scripts/mysql_agent.py describe-table --database app --table orders
```

将 SQL 和参数分别放在文件中，以便由 MySQL 驱动绑定参数，而不是拼接字符串。位置占位符 `%s` 对应 JSON 数组：

```sql
SELECT id, status
FROM orders
WHERE created_at >= %s
ORDER BY created_at DESC
```

```json
["2026-09-01"]
```

```powershell
python scripts/mysql_agent.py explain --sql-file .\query.sql --params-json .\params.json --limit 100
python scripts/mysql_agent.py query --sql-file .\query.sql --params-json .\params.json --limit 100
python scripts/mysql_agent.py export --sql-file .\query.sql --params-json .\params.json --limit 100 --format csv --output .\result.csv
```

也支持命名占位符；此时参数文件必须是 JSON 对象：

```sql
SELECT id, status
FROM orders
WHERE customer_id = %(customer_id)s
LIMIT 20
```

```json
{"customer_id": 42}
```

## 输出、限制与导出

每个命令返回如下结构；成功时 `error` 为 `null`，失败时进程以非零状态码退出：

```json
{
  "ok": true,
  "data": [],
  "meta": {"elapsed_ms": 12.34},
  "error": null
}
```

- `data`：命令结果。查询、结构发现和 `EXPLAIN` 返回对象数组；`ping` 和 `config validate` 返回对象。
- `meta`：执行元数据。查询类命令还会包含实际 `limit`、`truncated` 和 SQL 指纹；`truncated: true` 表示结果可能不完整，应缩小条件或采用分页查询。
- `error`：失败时包含稳定的 `code`、已脱敏的 `message` 和 `retryable` 标识。常见代码包括 `CONFIG_MISSING`、`CONNECTION_FAILED`、`SQL_REJECTED`、`LIMIT_EXCEEDED`、`OUTPUT_EXISTS` 与 `EXPORT_TOO_LARGE`。

`--limit` 必须为正整数，且不超过 `MYSQL_MAX_ROWS`。若 SQL 没有 `LIMIT`，脚本会追加该限制；若 SQL 已有 `LIMIT`，其返回行数不能超过 `--limit`。对潜在大范围查询，先运行 `explain`。

`export` 支持 `csv` 和 `jsonl`。输出文件必须尚不存在，且编码后的内容不能超过 `MYSQL_MAX_EXPORT_BYTES`；这两个限制可避免意外覆盖与过大导出。空结果会产生空文件。

## 审计日志

为需要本地审计的运行添加全局 `--audit-log` 选项：

```powershell
python scripts/mysql_agent.py --audit-log .\mysql-audit.jsonl query --sql-file .\query.sql --params-json .\params.json --limit 100
```

日志采用 JSON Lines 格式，仅记录时间、操作类型、只读执行模式、SQL 指纹、耗时和错误代码；不会记录密码、原始参数、原始 SQL 或查询结果。请将日志文件置于受控目录，并按组织的保留策略处理。

## 安全限制

- 仅接受单条 `SELECT` 或 `WITH ... SELECT`。
- 拒绝写操作、多语句、注释、锁定子句、文件函数、用户变量和存储例程。
- 查询缺少 `LIMIT` 时自动追加限制；无效的限制值会在连接前被拒绝。
- 导出不会覆盖既有文件，且受最大导出大小限制。
- 审计日志只记录 SQL 指纹等脱敏元数据，不记录密码、原始参数或查询结果。

脚本校验不能代替数据库最小权限。生产环境应使用仅授予目标 schema `SELECT` 权限的专用账号。写入、授权或生产连接仍需用户明确确认。

## 推荐使用流程

1. 执行 `config validate` 和 `ping`，确认变量与连接可用。
2. 对未知库表，依次使用 `list-databases`、`list-tables`、`describe-table`；不要猜测表名或列名。
3. 将单条参数化查询和参数分别写入文件。可能返回较多数据时，先执行 `explain`。
4. 使用尽可能小的 `--limit` 执行 `query`，并检查 `meta.truncated`。
5. 只有在确实需要落盘时才使用 `export`，同时选择受控的输出路径与审计日志位置。

## 测试

运行本地单元测试：

```powershell
python -m unittest discover -s tests -v
```

应将 `tests/` 与业务代码一同提交到 GitHub。它不是部署时的运行依赖，但能让他人和 CI 验证安全边界与后续修改没有回归。
## 隔离工作区、变更审批与回滚

所有运行产生的 SQL、参数、确认记录、回滚工件和 JSONL 审计日志都应放在独立工作区中。不要在原项目目录直接生成临时 SQL、导出或运行记录。

```powershell
# 使用单独目录；若该目录是 Git 仓库，状态文件会记录基线提交和分支
$workspace = "D:\mysql-agent-runs\change-20260925"
python scripts/mysql_agent.py workspace init --workspace-dir $workspace
python scripts/mysql_agent.py workspace status --workspace-dir $workspace
python scripts/mysql_agent.py workspace snapshot --workspace-dir $workspace --message "before-order-status-update"
```

运行工件保存在 `$workspace\.mysql-agent\`：`changes/<run-id>/` 归档 SQL、参数和回滚 SQL，`approvals/` 保存一次性确认记录，`runs/` 保存 JSON Lines 审计记录；`workspace snapshot` 会在 Git 工作区记录基线、分支、文件变更摘要和差异指纹，不会自动提交或改写分支。只读数据库命令也会自动写入工作区审计日志。不要把凭据、未脱敏参数或数据导出提交到版本库。

### 表、视图与例程结构

```powershell
python scripts/mysql_agent.py --workspace-dir $workspace list-tables --database app
python scripts/mysql_agent.py --workspace-dir $workspace describe-table --database app --table orders
python scripts/mysql_agent.py --workspace-dir $workspace show-create-table --database app --table orders
python scripts/mysql_agent.py --workspace-dir $workspace list-views --database app
python scripts/mysql_agent.py --workspace-dir $workspace list-routines --database app --type procedure
python scripts/mysql_agent.py --workspace-dir $workspace show-create-routine --database app --type procedure --name monthly_report
```

先读取对象结构再让 Agent 生成 SQL；不要猜测对象或列名。

### 受控数据变更与 DDL

Agent 将待执行语句与参数写入文件；工具不拼接业务 SQL。任何变更先预览：

```powershell
python scripts/mysql_agent.py preview --workspace-dir $workspace --sql-file .\update.sql --params-json .\params.json
```

预览会返回 `run_id`、风险等级、工件目录和（高/极高风险时）一次性 `confirmation_id`。确认令牌绑定 SQL 指纹、参数指纹、目标数据库和 15 分钟有效期；SQL、参数或目标发生变化时，必须重新预览并重新确认。

高风险（例如 `UPDATE`、`DELETE`、`ALTER`）和极高风险（例如 `DROP`、`TRUNCATE`、用户及授权变更）必须由用户明确确认。提交前还必须提供由 Agent 生成并审核过的回滚 SQL：

```powershell
python scripts/mysql_agent.py execute `
  --workspace-dir $workspace `
  --sql-file .\update.sql --params-json .\params.json `
  --run-id <run-id> --confirm <confirmation-id> `
  --rollback-sql-file .\rollback-update.sql --commit
```

`--commit` 是高/极高风险操作的强制显式提交开关；执行异常时工具会回滚未提交事务。已提交 DML 使用归档的补偿 SQL 恢复；极高风险操作还必须通过 `--backup-file` 指向已存在的备份工件。`TRUNCATE` 与部分 DDL 会发生隐式提交，不能依赖事务回滚，必须先完成备份并制定人工恢复方案。使用以下命令定位归档的补偿脚本；恢复脚本本身也必须重新预览并取得确认：

```powershell
python scripts/mysql_agent.py rollback --workspace-dir $workspace --run-id <run-id>
```

无 `WHERE` 的 `UPDATE` / `DELETE`、不可逆对象删除和权限操作应在运行策略中保持默认拒绝；本接口的确认流程不能替代数据库备份、最小权限账户或生产变更管理。
---
name: mysql-readonly
description: 通过脚本强制执行的只读策略安全检查和查询 MySQL 数据库。适用于 MySQL 连通性、结构发现和数据查询；不可用于修改数据。
---

# MySQL 只读查询

所有数据库操作都使用 `scripts/mysql_agent.py`。该脚本向 stdout 返回 JSON；应根据 `ok`、`data`、`meta` 和 `error` 字段判断结果，而不是解析自由文本错误信息。

## 工作流

1. 连接信息可能不完整时，操作前运行 `config validate`；首次使用某个连接前运行 `ping`。配置来自 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD` 以及可选的 `MYSQL_DATABASE`。绝不打印或持久化密码。
2. 查询未知数据前，使用 `list-databases`、`list-tables` 和 `describe-table` 发现库表结构。不得猜测表名或列名。
3. 将单条参数化 `SELECT`（或 `WITH ... SELECT`）写入本地 SQL 文件，将参数值写入 JSON 文件。对可能范围较大的查询先使用 `explain`，再以有界的 `--limit` 执行 `query`。
4. `truncated: true` 表示结果不完整。应缩小范围或分页查询，不得假设已返回全部结果。

CLI 会拒绝写操作、多语句、注释、锁定子句、文件函数、用户变量和无界输出。它不能替代只授予 `SELECT` 权限的 MySQL 账号。

写入、权限变更、创建凭据或连接生产系统均需用户明确授权。此初版 skill 不提供写操作命令。

配置连接时阅读[配置说明](references/configuration.md)；准备查询或理解拒绝原因时阅读[查询策略](references/query-policy.md)。

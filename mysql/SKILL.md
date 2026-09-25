---
name: mysql-controlled-agent
description: 通过隔离工作区、运行审计和显式确认机制安全检查、查询及受控变更 MySQL。适用于结构发现、只读查询和经用户确认的 DML/DDL；不应绕过生产变更流程。
---

# MySQL 受控操作

所有操作使用 `scripts/mysql_agent.py`，SQL 由 Agent 写入本地文件，参数由 JSON 文件提供。脚本输出 JSON；根据 `ok`、`data`、`meta` 和 `error` 决策，不能解析自由文本错误。

## 强制工作流

1. 在独立目录运行 `workspace init --workspace-dir <dir>`。不要在原项目目录生成 SQL、导出或日志。该目录中的 `.mysql-agent/` 保存运行审计、输入归档、确认记录和回滚工件；Git 可用时记录基线版本。
2. 对未知对象，先读取数据库、表、视图、例程定义和列结构，禁止猜测标识符。
3. 查询使用 `query`、`explain` 和最小必要 `--limit`。大范围查询先执行 `explain`，并检查 `truncated`。
4. 变更必须先使用 `preview`。高/极高风险预览会创建一次性确认令牌；向用户展示目标环境、对象、SQL 摘要、风险、影响范围及回滚方式后，才可请求确认。
5. 高/极高风险操作必须使用匹配的 `run-id`、`confirmation_id`、回滚 SQL 文件和 `--commit`。SQL、参数、环境或令牌过期后都必须重新预览。
6. 失败的事务执行会回滚。提交后的 DML 仅能通过归档的补偿 SQL 恢复；遇到隐式提交 DDL 或 `TRUNCATE`，没有已验证备份和人工恢复方案则拒绝执行。

## 风险

- 低：元数据读取、有界查询和执行计划。
- 中：INSERT、REPLACE、CREATE 等可评估变更。
- 高：UPDATE、DELETE、ALTER；必须确认和回滚方案。
- 极高：DROP、TRUNCATE、账户与授权变更；必须确认、备份与回滚/人工恢复方案。

不得把确认令牌复用于不同 SQL、参数或环境。默认拒绝无 `WHERE` 的 UPDATE/DELETE、不可逆删除和权限变更；数据库最小权限、备份和生产审批仍是必要前提。
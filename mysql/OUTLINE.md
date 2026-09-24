# MySQL Agent Skill — 能力大纲（脚本优先）

## 目标与原则

构建一个用于连接和查询 MySQL 的 Codex skill。它应把连接校验、元数据发现、SQL 执行、结果格式化和导出等可重复操作交给确定性脚本；模型仅用于把自然语言请求转为受约束的查询计划、在不明确时提问，以及解释脚本返回的结果。默认只读，任何写操作须在执行前获得用户明确确认。

## 目录建议

```text
mysql/
├── SKILL.md                 # 入口：意图路由、权限边界、调用脚本的规则
├── scripts/
│   ├── mysql_agent.py       # 唯一 CLI 入口，承载下列子命令
│   └── requirements.txt     # mysql-connector-python 或 PyMySQL
└── references/
    ├── configuration.md     # 连接配置与密钥约定
    ├── query-policy.md      # SQL 安全策略和写操作确认流程
    └── output-contract.md   # JSON/CSV/Markdown 输出字段约定
```

## 能力与实现方式

| 能力 | 默认行为 | 脚本实现 | 模型参与度 |
| --- | --- | --- | --- |
| 1. 配置发现与连接 | 从环境变量或指定的本地配置读取连接信息；不在命令行、日志或结果中回显密码 | `config validate`：读取 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE`，校验必填项并生成脱敏连接摘要 | 无；仅在配置缺失时说明缺什么 |
| 2. 连通性测试 | 执行最小查询并报告服务版本、当前用户、当前数据库和延迟 | `ping`：建立短连接，执行 `SELECT VERSION(), CURRENT_USER(), DATABASE()` | 无 |
| 3. 数据库与表发现 | 列出可访问数据库、表、视图和表的粗略行数；不扫描业务数据 | `list-databases`、`list-tables`：查询 `information_schema`，使用参数化过滤 | 可根据用户问题选择相应子命令 |
| 4. 表结构与关系检查 | 返回列、类型、可空性、默认值、主键、索引、外键及建表 DDL（按需） | `describe-table`：读取 `information_schema.columns/statistics/key_column_usage`；`show-create-table` 单独提供 | 选择表；不猜测表名 |
| 5. 安全的只读查询 | 默认仅允许单条 `SELECT` / `WITH … SELECT`，禁止多语句、注释绕过和锁表语句；强制行数上限 | `query`：词法预检 + 单语句校验 + 只读 allowlist；通过 driver 执行；自动附加或校验 `LIMIT`；设置连接与查询超时 | 将自然语言转为 SQL 草案；脚本是最终裁决者 |
| 6. 参数化查询 | 将值与 SQL 模板分离，避免注入和字符串拼接 | `query --sql-file … --params-json …`：使用 DB driver 参数绑定；参数 JSON 做类型校验 | 仅生成 SQL 模板与参数对象，不直接拼接值 |
| 7. 查询预检与成本控制 | 在执行前能查看语法/执行计划；对大查询要求用户确认 | `explain`：执行 `EXPLAIN FORMAT=JSON`；解析估算行数和索引使用情况；`query` 根据阈值拒绝或要求 `--confirm-large-query` | 解释计划与给出优化建议 |
| 8. 结果交付 | 一律结构化输出，便于模型可靠解读；大结果分页或导出，不把海量数据塞进上下文 | stdout 输出稳定 JSON（含列、行、总数、耗时、截断标志）；`export` 输出 CSV/JSONL 到用户指定路径 | 对结构化结果做摘要、计算或呈现 |
| 9. 审计与可复现 | 记录脱敏后的操作元数据，支持复跑同一查询 | `--audit-log`：记录时间、调用者、SQL 指纹、参数类型、行数、耗时、状态；不记录密码或原始敏感参数 | 无 |
| 10. 写操作（可选且关闭） | 初版不提供；未来启用时只能运行用户已确认的单语句 DML，并要求事务与影响行数上限 | 独立 `mutate` 子命令，需 `--allow-write --confirm <随机确认码>`；默认事务，先 dry-run/检查，超限回滚 | 可以生成建议 SQL，但每次执行都必须重新确认 |

## 推荐的脚本接口

```powershell
# 连接和元数据
python scripts/mysql_agent.py config validate
python scripts/mysql_agent.py ping
python scripts/mysql_agent.py list-databases
python scripts/mysql_agent.py list-tables --database app
python scripts/mysql_agent.py describe-table --database app --table orders

# 查询与预检：SQL 与参数均从文件传入，避免 shell 转义和意外泄漏
python scripts/mysql_agent.py explain --sql-file .\query.sql --params-json .\params.json
python scripts/mysql_agent.py query --sql-file .\query.sql --params-json .\params.json --limit 200
python scripts/mysql_agent.py export --sql-file .\query.sql --format csv --output .\result.csv
```

所有命令返回 JSON，成功和失败都遵循固定结构：`ok`、`data`、`meta`、`error`。脚本以非零退出码表示失败；skill 不从自由文本错误中猜测状态。

## SQL 安全边界

1. 初版只读：只接受 `SELECT` 和 `WITH` 开头且最终为 `SELECT` 的单条语句。
2. 拒绝 `INSERT`、`UPDATE`、`DELETE`、`REPLACE`、DDL、存储过程调用、`INTO OUTFILE`、`LOAD_FILE`、用户变量、`LOCK` 与多语句。
3. 只读数据库账号必须是部署前提：仅授予目标 schema 的 `SELECT`（必要时 `SHOW VIEW`）；脚本校验不能替代最小权限。
4. 参数必须通过驱动绑定；表名、列名等标识符不可参数化，因此只允许来自元数据发现结果的精确匹配值。
5. 设置连接超时、读取超时、最大返回行数与最大导出文件大小；结果含截断标志。
6. 禁止在任何输出、审计日志或异常堆栈中泄露密码、完整 DSN 或原始敏感参数。

## 模型与脚本的职责分界

```text
用户问题 → 模型：澄清目标 / 选择表 / 生成参数化 SQL 草案
         → 脚本：校验配置、验证 SQL、预检、执行、限流、结构化返回
         → 模型：基于 JSON 总结结果，并明确数据截断或执行限制
```

遇到不确定表或字段时，skill 必须先调用发现/结构子命令；不能凭空编造 schema。遇到写入、权限提升、凭证创建或连接生产库等影响性操作，先停下请求用户明确授权。

## 实施阶段

1. **MVP（建议先做）**：配置读取、`ping`、数据库/表/结构发现、受限只读 `query`、JSON 输出、基础测试。
2. **可靠性增强**：`explain`、查询阈值、分页/CSV 导出、脱敏审计、错误码标准化。
3. **可选写入**：独立的双重确认流程、事务与回滚、影响行数上限、写审计。只有明确业务需求后才实现。

## 验收标准

- 在无密码回显的前提下，能成功验证连接并发现 schema。
- 任意 DML/DDL、多语句、危险函数和越权 schema 都被脚本拒绝。
- 合法参数化查询返回可机器解析 JSON，且默认行数有限制。
- 连接失败、超时、语法错误、权限错误和结果截断各有稳定错误码/元数据。
- 单元测试覆盖 SQL allowlist/denylist、标识符白名单、脱敏、超时和 JSON 契约；集成测试使用临时 MySQL 实例与只读账号。

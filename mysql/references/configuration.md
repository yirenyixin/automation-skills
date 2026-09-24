# 连接配置

通过进程环境变量设置连接值；不要将其写入命令历史或提交到源代码管理的文件。

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

使用仅对目标 schema 授予 `SELECT` 权限（以及结构发现所需最少元数据权限）的专用账号。`config validate` 会输出脱敏连接摘要并校验数值设置，不会建立连接。

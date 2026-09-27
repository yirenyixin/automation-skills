---
name: run-observability
description: 在 WorkBuddy 使用本地模型执行多步骤任务、外部命令、文件操作或预计超过一分钟的工作时，记录状态检查点、退出码、错误原因和中断线索，避免任务无说明停止。也用于诊断程序错误、工具错误、权限问题、等待输入、超时以及疑似模型或宿主中断。
disable-model-invocation: false
---

# 运行可观测性

## WorkBuddy 强制启动检查点

Skill 被触发时，WorkBuddy 必须先执行以下初始化命令。该命令的输出是本次任务的运行目录：

!`python "${CODEBUDDY_SKILL_DIR}/scripts/run_status.py" init --task "WorkBuddy 本地模型任务"`

将上方命令输出的路径作为本次 `RUN_DIR`。如果命令没有返回路径，必须立即告诉用户“状态记录器未启动”，说明可能是 Python、权限或 Skill 路径问题；不得继续声称即将执行其他操作，也不得把任务报告为已完成。

本 skill 让任务即使意外停止，也能从磁盘状态判断最后阶段。它不能捕获进程被强杀、宿主崩溃或硬性上下文截断本身，但能通过“最后检查点仍为运行中且长期未更新”将这类情况与已记录的程序错误区分开。

在 WorkBuddy 中安装并启用本 skill 后，允许模型根据任务自动触发。为了确保某次本地模型任务使用它，可在新建任务栏的技能区域显式选中运行可观测性。

## 必须遵守的工作方式

1. 在 WorkBuddy 中直接使用上方预执行命令返回的 `RUN_DIR`，不得重复初始化。只有不支持内联命令的其他宿主才手动运行 `python "<skill目录>/scripts/run_status.py" init --task "<脱敏任务摘要>"`。
2. 保存返回的运行目录。在每个实质阶段开始前更新检查点：`python "${CODEBUDDY_SKILL_DIR}/scripts/run_status.py" update <运行目录> --state running --phase "<当前阶段>" --next-action "<下一步>"`。
3. 预计较慢或可能阻塞的命令优先通过 `python "${CODEBUDDY_SKILL_DIR}/scripts/run_command.py" --run <RUN_DIR> --phase "<阶段>" -- <命令及参数>` 执行。它会在命令前后更新状态，并保留真实退出码。
4. 需要用户输入或权限时，将状态更新为 `waiting_user`，说明缺少什么；不得无说明结束。
5. 发生错误时，先根据实际证据选择 `error-kind`，写入脱敏原因和可执行的下一步，然后再回复用户。不得把未知中断伪装成程序错误或上下文超限。
6. 正常完成时必须写入 `complete`；验证失败写入 `failed/validation_failed`；用户取消写入 `cancelled`。

## 状态与原因

允许的状态：`running`、`waiting_user`、`blocked`、`failed`、`complete`、`interrupted`、`cancelled`。

允许的错误类别：`none`、`command_error`、`tool_error`、`permission_denied`、`timeout`、`dependency_missing`、`validation_failed`、`context_risk`、`user_input_required`、`external_interrupt`、`unknown`。

仅当有明确的上下文用量告警、截断事件或宿主证据时使用 `context_risk`。只有“突然停止”而无证据时，保持 `running`；之后由 `diagnose` 将其识别为过期运行并给出多种可能原因。

## 用户可见报告

每次最终回复都必须明确属于以下一种：已完成、需要用户操作、已阻塞、执行失败、已取消。失败报告至少包含失败阶段、错误类别、已完成部分、未完成部分和下一步。不要只说“出错了”或直接停止。

禁止以“让我先……”“接下来我会……”“我现在去……”等只描述未来动作的文字结束一轮。只要尚未产生工具调用结果，就不得声称动作已经开始；必须实际调用工具，或明确报告无法调用工具的原因。
WorkBuddy 可能折叠或隐藏模型的深度思考，因此错误证据、退出码和停止原因不得只留在思考过程。任何工具或命令失败后，必须先把脱敏后的关键信息写入状态文件，并在用户可见回复中给出简短摘要。不得依赖用户展开思考过程才能知道任务为何停止。

如果模型已经在思考中判断出可修正原因（例如把 PowerShell 的 Select-String 放进 Bash，导致退出码 127），必须在同一轮真正发起修正后的工具调用并读取结果。若没有新的工具结果，则只能明确报告“执行失败”或“需要用户操作”，不能输出“继续执行”“让我先重试”等承诺性文字。对同一已确认的命令构造错误最多自动重试一次，避免无限循环。

运行中断后执行：`python "${CODEBUDDY_SKILL_DIR}/scripts/run_status.py" diagnose <运行目录> --stale-seconds 300`。

诊断解释见 [中断诊断](references/diagnosis.md)。状态文件不得记录密码、令牌、完整邮件正文、附件内容或其他秘密。




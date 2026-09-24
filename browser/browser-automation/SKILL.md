---
name: browser-automation
description: 通过可用的 Edge 或 Chrome MCP，以 DOM 优先且可验证的工作流执行浏览器操作。适用于浏览、提取、表单、下载和需要隔离文件及可回滚修改的浏览器任务。
---

# 浏览器自动化

使用此 skill 通过可用的 Edge 或 Chrome MCP 执行浏览器任务。优先使用其结构化浏览器操作、页面 DOM、无障碍信息和脚本执行能力，避免依赖视觉推理或坐标点击。

## 每次运行均从隔离工作区开始

不得直接修改此 skill 的文件、输入文件或既有运行目录。先创建运行目录：

```powershell
node scripts/workspace_manager.mjs create --runs-dir runs --task <short-task-name>
```

该命令会输出包含 `runRoot`、`workRoot` 和 `runId` 的 JSON。使用 `workspace_manager.mjs import` 导入用户提供的输入；输出、下载、临时文件和派生文件只能写入本次运行的 `work/` 目录。

修改 `work/` 下已有文件前，必须用 `version_manager.mjs snapshot` 创建快照。不得通过其他方式覆盖、移动、格式化或删除该文件。使用 `rollback.mjs` 恢复指定版本；回滚本身也会创建新的快照。

## MCP 工具预检：严禁猜测工具名

执行浏览器操作前，先检查当前会话实际暴露的工具目录，只能调用目录中返回的精确工具名和参数。不得尝试调用 `browser`、`edge`、`chrome` 或其他未在当前工具目录出现的推测名称。

- 若当前会话有来自 `chrome-devtools` 或 `edge-devtools` 的实际 MCP 工具，读取其工具说明并使用其精确名称与参数。
- 若没有对应工具，先运行 `scripts/setup_browser_mcp.ps1` 注册实际 MCP；Chrome 使用 `-Browser chrome`，Edge 使用 `-Browser edge`。该脚本使用 Google 维护的 `chrome-devtools-mcp`；Edge 通过本机 DevTools 调试端口连接。
- 注册或变更 MCP 后，立即停止当前浏览器任务并告知用户**新开 Codex 会话**。当前会话不能假定工具清单会刷新，更不能猜测新工具名称。
- 使用 Edge 时，如未启动调试端口，在当前运行目录下创建独立 profile 后运行：`powershell -File scripts/setup_browser_mcp.ps1 -Browser edge -StartEdge -EdgeProfilePath <runRoot>\edge-profile`。不得连接用户日常 Edge 配置文件。
## 浏览器操作流程

1. 选择用户明确指定的浏览器。若未指定，则选择可用的 Edge 或 Chrome MCP 会话，并在运行日志中记录选择结果。
2. 通过 tab ID、URL 或标题确定目标标签页。交互前先检查 DOM 或无障碍树。
3. 按如下顺序定位目标：测试 ID 或 ID；角色加无障碍名称；标签或名称；稳定 CSS；可见文本。仅当结构化方法失效时才使用截图和坐标。
4. 每次导航、点击、提交、上传或下载后，验证可观察条件：URL、元素状态、文本、表单值或已下载文件。
5. 将工作流步骤记录在 `workflow.json`，证据记录在 `evidence/`，结果记录在 `result.json`。参见[工作流格式](references/workflow-schema.md)。

## 人工验证与外部副作用

如果出现 CAPTCHA、滑块、reCAPTCHA、hCaptcha、Turnstile 或 OTP 挑战，遵循[验证挑战规则](references/challenge-policy.md)：保留证据、暂停并等待用户完成验证，确认已解除后再恢复。不得自动破解、绕过或规避 CAPTCHA。

发送消息、发布、支付、删除线上数据或提交有重要影响的表单等不可逆外部操作前，展示简要的最终操作摘要，并取得所需的用户确认。

## 参考资料

- 适配 Edge 或 Chrome MCP 时，阅读 [MCP 接口约定](references/mcp-contract.md)。
- 常规定位失败时，阅读[定位策略](references/locator-strategy.md)。
- 需要路径、快照和导出规则时，阅读[工作区规则](references/workspace-policy.md)。


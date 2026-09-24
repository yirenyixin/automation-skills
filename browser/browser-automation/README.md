# 浏览器自动化

一个面向 Edge 和 Chrome MCP 的浏览器自动化 skill。它尽可能将浏览器工作确定化：DOM 优先定位、显式等待、结构化工作流步骤、动作断言和证据保存。浏览器 MCP 始终是浏览器控制层；附带的 Node 脚本负责创建隔离工作区、保存文件历史和校验工作流文件。

## 能做什么

- 在 Edge 或 Chrome 中打开、选择和切换目标标签页。
- 使用 DOM、无障碍角色、标签和稳定选择器定位页面元素，避免依赖坐标点击。
- 执行浏览、搜索、点击、输入、选择、滚动、表单填写和页面状态等待。
- 抓取正文、列表和表格数据，并保存为工作区内的 JSON、CSV 或 Markdown 文件。
- 管理上传、下载、截图、DOM 快照和操作证据。
- 使用 JSON 工作流描述重复性任务，并在每一步后验证 URL、元素、文本、表单值或下载结果。
- 检测 CAPTCHA、滑块、人机验证和 OTP；保留现场，等待用户在浏览器中完成验证后继续。
- 对运行期间修改的文件保留编号快照，并能随时回滚。

不支持自动破解、绕过或规避验证码。发送消息、发布、支付、删除或提交重要表单等外部操作，会在最后一步前要求用户确认。

## 如何让 agent 使用

在 Codex 对话中直接说明浏览器任务并指定浏览器即可，例如：

```text
使用 Edge 打开网站，导出本月订单表格到 CSV；所有文件保存在 browser 的本次工作区中。
```

或显式调用：

```text
使用 $browser-automation：在 Chrome 中登录网站，提取页面表格，保存为 CSV，并保留每次文件修改的可回滚版本。
```

agent 会先建立独立运行目录，再通过可用的 Edge 或 Chrome MCP 操作浏览器。若遇到登录、验证码或需要确认的外部提交，agent 会暂停并说明下一步需要你完成或确认的内容。

## 自动接入实际浏览器 MCP

该 skill 不会猜测浏览器工具名。首次使用时，可运行以下命令注册实际的 Chrome/Edge DevTools MCP：

```powershell
powershell -File scripts/setup_browser_mcp.ps1 -Browser both
```

Chrome 使用 Google 维护的 `chrome-devtools-mcp` 并由 `npx` 在首次调用时自动下载。Edge 使用同一 MCP 连接本机 `127.0.0.1:9222` 调试端口；需要新 Edge 实例时，使用本次运行目录中的独立 profile：

```powershell
powershell -File scripts/setup_browser_mcp.ps1 -Browser edge -StartEdge -EdgeProfilePath <runRoot>\edge-profile
```

配置完成后必须新开 Codex 会话。agent 在新会话中先读取当前工具目录，只能使用实际列出的 MCP 工具名称与参数；没有工具时会停止并提示接入，绝不猜测 `browser` 等工具名称。
## 前置条件

- Node.js 20 或更高版本。
- 可用的 Edge 或 Chrome 浏览器 MCP 会话。
- 任务所需外部操作的相应权限。

## 目录结构

- `SKILL.md`：供调用该 skill 的 agent 读取的操作说明。
- `scripts/`：跨环境的工作区、版本、回滚、挑战检测和工作流校验辅助脚本。
- `references/`：MCP 接口约定和执行限制。
- `runs/`：按需创建，每次调用一个独立目录。

skill 目录视为基础安装目录：不得向其中写入任务文件。一次运行具有以下结构：

```text
runs/<run-id>/
  input/       提供文件的不可变副本
  work/        唯一允许生成或修改文件的位置
  versions/    按原相对路径归类的快照
  evidence/    DOM 快照、截图和下载记录
  logs/        结构化事件日志
  workflow.json
  run-manifest.json
  result.json
```

## 快速开始

```powershell
node scripts/workspace_manager.mjs create --runs-dir runs --task export-orders
node scripts/workspace_manager.mjs import --run-root runs/<run-id> --source <file-or-directory>
node scripts/version_manager.mjs snapshot --run-root runs/<run-id> --file work/orders.csv --reason "before normalization"
node scripts/workflow_runner.mjs validate --workflow runs/<run-id>/workflow.json --run-root runs/<run-id>
```

随后通过 Edge 或 Chrome MCP 执行已校验的工作流。浏览器输出和下载必须写入 `work/`；截图和 DOM 证据写入 `evidence/`。

## 一次运行会产生什么

每个任务都会生成 `runs/<运行编号>/`。你通常只需关注：

- `work/`：最终导出、下载或修改后的文件。
- `versions/`：每次修改前的历史版本；可用于回滚。
- `evidence/`：截图、DOM 快照和下载证据。
- `workflow.json`：本次任务的结构化步骤。
- `result.json`：本次任务的完成结果。

## 文件历史与回滚

每次修改 `work/` 下已有文件前都必须创建快照。版本编号为 `v0001`、`v0002` 等；每个清单条目都会记录时间、原因、文件大小和 SHA-256。

```powershell
node scripts/version_manager.mjs list --run-root runs/<run-id> --file work/orders.csv
node scripts/rollback.mjs --run-root runs/<run-id> --file work/orders.csv --version v0001
```

回滚会先将当前文件保存为新版本，再把旧版本复制到 `work/`。不会进行不可恢复删除。

## CAPTCHA 与 OTP

该 skill 会检测常见验证挑战并暂停等待用户操作。它不会尝试破解、规避或自动化 CAPTCHA 挑战。对于短信、邮件或身份验证器代码，用户提供代码；agent 仅填写相应字段并验证结果状态。

## 外部操作

agent 必须在发送、发布、支付、删除或提交任何有重要影响的外部操作前立即请求确认。浏览和只读数据提取不需要这项最终操作确认。


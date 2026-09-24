# MCP 接口约定

本 skill 使用实际注册的 `chrome-devtools` 和 `edge-devtools` MCP。前者由 Google 维护的 `chrome-devtools-mcp` 提供；后者使用相同服务并连接本机 Edge 的 `http://127.0.0.1:9222` DevTools 端口。

每次调用前必须从**当前会话的工具目录**读取服务器提供的精确工具名、说明和参数。工具名称会因 MCP 客户端而异；不得在 skill、脚本或提示词中猜测并调用名为 `browser` 的工具。若工具目录中没有对应 MCP 工具，运行 `scripts/setup_browser_mcp.ps1` 配置后，要求用户新开会话。

使用返回的实际工具将其映射到概念操作：列出和激活标签页、导航、检查 DOM 或无障碍树、执行页面代码、点击、输入、选择、按键、滚动、截图和观察下载。每次改变状态的操作后，记录浏览器名称、标签页标识、URL 和操作结果。优先使用 MCP 返回的选择器或无障碍标识。

Edge 连接要求 Edge 以 `--remote-debugging-port=9222` 启动；请使用独立 profile，避免暴露用户的日常浏览器会话。Chrome DevTools MCP 的配置与 Codex 安装方式见 [Chrome DevTools 官方文档](https://developer.chrome.com/docs/devtools/agents/get-started)，Edge 配置见 [Microsoft Edge 官方文档](https://learn.microsoft.com/microsoft-edge/web-platform/devtools-mcp-server)。

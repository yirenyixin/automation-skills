[CmdletBinding()]
param(
  [ValidateSet('chrome', 'edge', 'both')]
  [string]$Browser = 'both',
  [switch]$StartEdge,
  [string]$EdgeProfilePath
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw '未找到 Codex CLI，无法注册 MCP。' }
if (-not (Get-Command npx -ErrorAction SilentlyContinue)) { throw '未找到 npx。请先安装 Node.js 20 或更高版本。' }

$configured = (& codex mcp list | Out-String)
function Add-ServerIfMissing([string]$name, [string[]]$arguments) {
  if ($configured -notmatch "(?m)^$([regex]::Escape($name))\s") {
    & codex mcp add $name -- @arguments
    if ($LASTEXITCODE -ne 0) { throw "注册 MCP 服务器失败：$name" }
  }
}

if ($Browser -in @('chrome', 'both')) {
  Add-ServerIfMissing 'chrome-devtools' @('cmd', '/c', 'npx', '-y', 'chrome-devtools-mcp@latest')
}
if ($Browser -in @('edge', 'both')) {
  Add-ServerIfMissing 'edge-devtools' @('cmd', '/c', 'npx', '-y', 'chrome-devtools-mcp@latest', '--browser-url=http://127.0.0.1:9222')
  if ($StartEdge) {
    if (-not $EdgeProfilePath) { throw '启动 Edge 时必须指定当前运行工作区下的 -EdgeProfilePath。' }
    $profile = [System.IO.Path]::GetFullPath($EdgeProfilePath)
    New-Item -ItemType Directory -Force -Path $profile | Out-Null
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $edge) { throw '未找到 msedge.exe。' }
    Start-Process -FilePath $edge -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=$profile"
  }
}

Write-Output 'MCP 配置完成。请新开 Codex 会话；本会话的工具清单不会自动刷新。'


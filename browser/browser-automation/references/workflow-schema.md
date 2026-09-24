# 工作流格式

工作流是 JSON，包含当前运行的 `runId`、`browser`（`edge` 或 `chrome`）和非空的 `steps` 数组。支持的操作有 `goto`、`click`、`fill`、`select`、`press`、`scroll`、`wait`、`assert`、`extract`、`upload`、`download`、`handle_challenge`、`checkpoint`、`resume` 和 `mutate_file`。

所有 `output`、`file` 和 `path` 字段都必须解析到当前运行的 `work/` 目录之下。`goto` 必须有 `url`；点击、填写和选择必须有 `target`，其中 `fill` 还必须有 `value`；`extract` 必须有位于 `work/` 的 `output`。

每次导航或交互等状态变更之后，都必须紧接一个 `handle_challenge`。该步骤必须声明 URL、tab ID、DOM 快照和截图证据；在检查确认挑战已解除前，适配器会拒绝下一次交互请求。需要修改文件时，先使用 `checkpoint`（`kind: "snapshot"`）声明对应文件的快照，再执行含非空 `reason` 的 `mutate_file`。

外部副作用为高影响的步骤必须设置 `effect: "high"`，并提供本次 `runId` 对应、含摘要和确认时间的 `confirmation` 记录；否则适配器会拒绝下发请求。

```json
{
  "runId": "20260924-export-orders",
  "browser": "edge",
  "steps": [
    { "op": "goto", "url": "https://example.com" },
    {
      "op": "handle_challenge",
      "evidence": {
        "url": "https://example.com",
        "tabId": "tab-1",
        "domSnapshot": "evidence/page.html",
        "screenshot": "evidence/page.png"
      }
    },
    { "op": "extract", "format": "csv", "output": "work/results.csv" },
    { "op": "checkpoint", "kind": "snapshot", "file": "work/results.csv" },
    { "op": "mutate_file", "file": "work/results.csv", "reason": "删除重复行" }
  ]
}
```

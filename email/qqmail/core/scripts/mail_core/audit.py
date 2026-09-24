from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write_audit(workspace: Path, *, operation: str, function: str, user_request: str, status: str, inputs: dict, result: dict | None = None, error: str | None = None) -> None:
    """Append a Chinese, secret-free JSONL audit record for one operation."""
    record = {
        "时间": datetime.now().astimezone().isoformat(),
        "工作区": workspace.name,
        "操作": operation,
        "调用功能": function,
        "用户请求": user_request or "未提供（调用方未填写请求摘要）",
        "状态": status,
        "输入摘要": inputs,
        "结果": result or {},
        "错误": error or "",
    }
    path = workspace / "logs" / "audit.jsonl"
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")

"""Non-destructive temporary workspace storage inspection."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_LIMIT_MB = 500
TEMPORARY_DIRECTORIES = ("downloads", "outputs", "logs", "drafts")


def _limit_mb(skill_root: Path) -> tuple[int, str | None]:
    policy = skill_root / "config" / "workspace-policy.json"
    try:
        value = json.loads(policy.read_text(encoding="utf-8"))
        limit = value.get("workspace_size_limit_mb")
        if isinstance(limit, int) and limit > 0:
            return limit, None
        return DEFAULT_LIMIT_MB, "容量阈值配置无效，已使用默认 500 MB。"
    except FileNotFoundError:
        return DEFAULT_LIMIT_MB, "未找到容量阈值配置，已使用默认 500 MB。"
    except (OSError, json.JSONDecodeError):
        return DEFAULT_LIMIT_MB, "无法读取容量阈值配置，已使用默认 500 MB。"


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def inspect_workspace_storage(skill_root: Path, workspace: Path) -> dict:
    """Report all task workspaces and safe cleanup candidates without deleting files."""
    workspaces = skill_root / "workspaces"
    limit_mb, configuration_warning = _limit_mb(skill_root)
    total = 0
    candidates: list[tuple[Path, int]] = []
    if workspaces.is_dir():
        for path in workspaces.rglob("*"):
            if not path.is_file():
                continue
            size = _file_size(path)
            total += size
            try:
                relative = path.relative_to(workspaces)
            except ValueError:
                continue
            if any(part in TEMPORARY_DIRECTORIES for part in relative.parts):
                candidates.append((path, size))
    limit_bytes = limit_mb * 1024 * 1024
    exceeded = total >= limit_bytes
    result = {
        "状态": "超出阈值" if exceeded else "正常",
        "检测范围": "workspaces/（全部任务工作区）",
        "当前执行工作区": str(workspace.relative_to(skill_root)).replace("\\", "/"),
        "当前占用MB": round(total / 1024 / 1024, 2),
        "阈值MB": limit_mb,
        "自动删除": "未执行",
    }
    if configuration_warning:
        result["配置提示"] = configuration_warning
    if exceeded:
        largest = sorted(candidates, key=lambda item: item[1], reverse=True)[:10]
        result["建议"] = "请明确选择删除下列临时文件，或授权修改 config/workspace-policy.json 的 workspace_size_limit_mb；系统不会自动删除。"
        result["可优先清理"] = [
            {
                "路径": str(path.relative_to(skill_root)).replace("\\", "/"),
                "大小MB": round(size / 1024 / 1024, 2),
            }
            for path, size in largest
        ]
    return result

from __future__ import annotations

import json
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def skill_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "SKILL.md").is_file():
            return candidate
    fail("无法定位 skill 根目录。")


def workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "manifest.json").is_file():
            return candidate
    fail("请在 workspaces/<任务名> 目录中执行。")


def safe_child(root: Path, requested: Path, allow_external: bool = False) -> Path:
    target = requested.resolve()
    if not allow_external:
        try:
            target.relative_to(root.resolve())
        except ValueError:
            fail("目标路径必须位于当前工作区内；工作区外路径需要 --allow-external-output。")
    return target


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(f"无法读取文件：{path}（{exc.strerror or exc}）")
    except json.JSONDecodeError as exc:
        fail(f"JSON 格式错误：{path}，第 {exc.lineno} 行第 {exc.colno} 列。")
    if not isinstance(value, dict):
        fail(f"JSON 顶层必须是对象：{path}")
    return value

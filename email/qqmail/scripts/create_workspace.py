#!/usr/bin/env python3
"""Create an isolated, versioned QQ Mail execution workspace from the stable core."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="创建邮件任务工作区")
    parser.add_argument("name", help="小写字母、数字和连字符组成的任务名称")
    parser.add_argument("--description", default="", help="本次任务说明")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.name):
        parser.error("name 只能包含小写字母、数字和连字符，且必须以字母或数字开头。")
    destination = ROOT / "workspaces" / args.name
    if destination.exists():
        parser.error(f"工作区已存在：{destination}")
    core = ROOT / "core"
    version = (core / "VERSION").read_text(encoding="utf-8").strip()
    (destination / "rules").mkdir(parents=True)
    (destination / "drafts").mkdir()
    (destination / "outputs").mkdir()
    (destination / "downloads").mkdir()
    (destination / "logs").mkdir()
    shutil.copytree(core, destination / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    manifest = {
        "workspace": args.name,
        "base_version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": args.description,
        "changes": [],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()

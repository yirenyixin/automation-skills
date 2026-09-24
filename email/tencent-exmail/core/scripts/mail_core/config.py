from __future__ import annotations

import os
from pathlib import Path

from .common import fail, load_json, skill_root


def load_config(script_path: Path) -> dict:
    root = skill_root(script_path.resolve())
    config = load_json(root / "config" / "config.json")
    password = os.getenv("EMAIL_SKILL_PASSWORD")
    if password:
        config.setdefault("account", {})["password"] = password
    for section in ("smtp", "imap", "account"):
        if not isinstance(config.get(section), dict):
            fail(f"配置缺少 {section} 对象。")
    account = config["account"]
    if not isinstance(account.get("email"), str) or "@" not in account["email"]:
        fail("请在 config/config.json 中填写完整账户邮箱。")
    if not isinstance(account.get("password"), str) or not account["password"] or account["password"].startswith("replace-with-"):
        fail("请在 config/config.json 或 EMAIL_SKILL_PASSWORD 中配置密码。")
    return config

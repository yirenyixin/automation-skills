from __future__ import annotations

from pathlib import Path

from .common import fail, load_json, skill_root


def load_config(script_path: Path) -> dict:
    root = skill_root(script_path.resolve())
    config = load_json(root / "config" / "config.json")
    for section in ("smtp", "imap", "account"):
        if not isinstance(config.get(section), dict):
            fail(f"配置缺少 {section} 对象。")
    account = config["account"]
    if not isinstance(account.get("email"), str) or "@" not in account["email"]:
        fail("请在 config/config.json 中填写完整账户邮箱。")
    authorization_code = account.get("authorization_code")
    if not isinstance(authorization_code, str) or not authorization_code or authorization_code.startswith("replace-with-"):
        fail("请在 config/config.json 中配置 QQ 邮箱客户端授权码；不得使用网页登录密码。")
    account["password"] = authorization_code
    del account["authorization_code"]
    return config

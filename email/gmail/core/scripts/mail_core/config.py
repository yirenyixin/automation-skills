from __future__ import annotations

from pathlib import Path

from .common import fail, load_json, skill_root


def load_config(script_path: Path) -> dict:
    root = skill_root(script_path.resolve())
    client_config = load_json(root / "config" / "oauth-client.json")
    token = load_json(root / "config" / "token.json")
    account_config = load_json(root / "config" / "account.json")
    client = client_config.get("installed") or client_config.get("web")
    if not isinstance(client, dict):
        fail("OAuth 客户端配置必须包含 installed 或 web 对象。")
    config = {
        "smtp": {"host": "smtp.gmail.com", "port": 465},
        "imap": {"host": "imap.gmail.com", "port": 993},
        "account": {"email": account_config.get("email", "")},
        "oauth": {"client": client, "token": token, "token_path": root / "config" / "token.json"},
    }
    for section in ("smtp", "imap", "account"):
        if not isinstance(config.get(section), dict):
            fail(f"配置缺少 {section} 对象。")
    account = config["account"]
    if not isinstance(account.get("email"), str) or "@" not in account["email"]:
        fail("请在 config/config.json 中填写完整账户邮箱。")
    return config

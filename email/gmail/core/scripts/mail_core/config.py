from __future__ import annotations

from pathlib import Path

from .common import fail, load_json, skill_root


def load_config(script_path: Path) -> dict:
    root = skill_root(script_path.resolve())
    value = load_json(root / "config" / "imap-smtp.local.json")
    account = {"email": value.get("gmail_address", "")}
    imap = value.get("imap", {"host": "imap.gmail.com", "port": 993})
    smtp = value.get("smtp", {"host": "smtp.gmail.com", "port": 465})
    if not isinstance(account["email"], str) or "@" not in account["email"]:
        fail("请在 config/imap-smtp.local.json 中填写完整 gmail_address。")
    if not isinstance(value.get("app_password"), str) or not value["app_password"].strip():
        fail("请在 config/imap-smtp.local.json 中填写 app_password。")
    if not isinstance(imap, dict) or not isinstance(smtp, dict):
        fail("本地配置中的 imap 和 smtp 必须是对象。")
    return {"account": account, "app_password": value["app_password"].replace(" ", ""), "imap": imap, "smtp": smtp}

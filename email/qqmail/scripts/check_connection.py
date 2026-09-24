#!/usr/bin/env python3
"""Verify QQ Mail IMAP/SMTP authentication without reading or sending mail."""

from __future__ import annotations

import imaplib
import json
import smtplib
import ssl
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check_imap(config: dict) -> str:
    client = None
    try:
        client = imaplib.IMAP4_SSL(config["imap"]["host"], int(config["imap"]["port"]), ssl_context=ssl.create_default_context(), timeout=20)
        client.login(config["account"]["email"], config["account"]["authorization_code"])
        return "连接和认证成功"
    except Exception:
        return "连接或认证失败"
    finally:
        try:
            if client is not None:
                client.logout()
        except Exception:
            pass


def check_smtp(config: dict) -> str:
    client = None
    try:
        client = smtplib.SMTP_SSL(config["smtp"]["host"], int(config["smtp"]["port"]), context=ssl.create_default_context(), timeout=20)
        client.login(config["account"]["email"], config["account"]["authorization_code"])
        return "连接和认证成功"
    except Exception:
        return "连接或认证失败"
    finally:
        try:
            if client is not None:
                client.quit()
        except Exception:
            pass


def main() -> None:
    try:
        config = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError
        for group, key in (("imap", "host"), ("smtp", "host"), ("account", "email"), ("account", "authorization_code")):
            if not config.get(group, {}).get(key):
                raise ValueError
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"状态": "【需要用户操作】", "错误类别": "QQ 邮箱本地配置缺失或无效", "说明": "未连接邮箱，未显示授权码。"}, ensure_ascii=False))
        return
    print(json.dumps({"状态": "【连接检查完成】", "IMAP": check_imap(config), "SMTP": check_smtp(config), "读取邮件": "未执行", "发送邮件": "未执行", "授权码": "未显示"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

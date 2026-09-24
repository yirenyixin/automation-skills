#!/usr/bin/env python3
"""Report provider configuration readiness without exposing credentials."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = {
    "tencent-exmail": {
        "files": ["tencent-exmail/config/config.json"],
        "fields": [("tencent-exmail/config/config.json", ("smtp", "host")), ("tencent-exmail/config/config.json", ("imap", "host")), ("tencent-exmail/config/config.json", ("account", "email"))],
    },
    "qqmail": {
        "files": ["qqmail/config/config.json"],
        "fields": [("qqmail/config/config.json", ("smtp", "host")), ("qqmail/config/config.json", ("imap", "host")), ("qqmail/config/config.json", ("account", "email")), ("qqmail/config/config.json", ("account", "authorization_code"))],
    },
    "gmail": {
        "files": ["gmail/config/oauth-client.json", "gmail/config/token.json", "gmail/config/account.json"],
        "fields": [("gmail/config/account.json", ("email",))],
    },
}


def read_json(path: Path) -> tuple[dict | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "文件不存在"
    except (OSError, json.JSONDecodeError):
        return None, "文件不可读取或 JSON 格式无效"
    return data if isinstance(data, dict) else None, "顶层不是 JSON 对象"


def value_at(data: dict, keys: tuple[str, ...]) -> bool:
    current = data
    for key in keys:
        if not isinstance(current, dict) or not current.get(key):
            return False
        current = current[key]
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="无敏感信息的邮箱配置状态检查")
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--request-note", default="", help="脱敏的用户请求摘要，写入初始化日志")
    args = parser.parse_args()
    spec = PROVIDERS[args.provider]
    loaded: dict[str, dict] = {}
    missing: list[str] = []
    errors: list[str] = []
    for relative in spec["files"]:
        data, error = read_json(ROOT / relative)
        if data is None:
            (missing if error == "文件不存在" else errors).append(relative)
        else:
            loaded[relative] = data
    for relative, keys in spec["fields"]:
        if relative in loaded and not value_at(loaded[relative], keys):
            missing.append(f"{relative}：{'.'.join(keys)}")
    if errors:
        result = {"状态标记": "【配置失败】", "服务商": args.provider, "错误类别": "配置格式错误", "错误文件": errors, "下一步": "检查本地 JSON 文件格式；不要在对话中提供秘密。"}
    elif missing:
        result = {"状态标记": "【需要用户操作】", "服务商": args.provider, "缺失项": missing, "下一步": "在该服务商的本地配置文件完成配置后重新检查。"}
    else:
        result = {"状态标记": "【配置完成】", "服务商": args.provider, "配置文件": spec["files"], "认证信息": "已配置（未显示具体值）", "连接测试": "未执行", "下一步": "可使用对应服务商 skill 执行后续操作。"}
    log = {
        "时间": datetime.now().astimezone().isoformat(),
        "服务商": args.provider,
        "执行步骤": "检查配置状态",
        "用户请求": args.request_note or "未提供（调用方未填写请求摘要）",
        "状态": result["状态标记"],
        "错误类别": result.get("错误类别", ""),
        "下一步": result["下一步"],
    }
    try:
        log_path = ROOT / args.provider / "logs" / "setup-audit.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(log, ensure_ascii=False) + "\n")
        result["初始化日志"] = str(log_path)
    except OSError:
        result["初始化日志"] = "未能写入；请检查服务商目录权限。"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

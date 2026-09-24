#!/usr/bin/env python3
"""Unified workspace CLI for deterministic QQ Mail operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mail_core.audit import write_audit
from mail_core.common import fail, load_json, safe_child, skill_root, workspace_root
from mail_core.config import load_config
from mail_core.reader import download, save_result, search
from mail_core.sender import send
from mail_core.storage import inspect_workspace_storage


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description="QQ 邮箱工作区工具")
    main.add_argument("--request-note", default="", help="经脱敏的用户请求摘要，写入中文审计日志")
    actions = main.add_subparsers(dest="action", required=True)
    send_parser = actions.add_parser("send", help="预览或发送邮件")
    send_parser.add_argument("--to", action="append", required=True)
    send_parser.add_argument("--cc", action="append", default=[])
    send_parser.add_argument("--bcc", action="append", default=[])
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--text", default="")
    send_parser.add_argument("--html")
    send_parser.add_argument("--attachment", action="append", default=[])
    send_parser.add_argument("--max-attachment-mb", type=int, default=20)
    send_parser.add_argument("--timeout", type=int, default=30)
    send_parser.add_argument("--confirm-send", action="store_true", help="明确提交给 SMTP")
    for name, help_text in (("search", "按规则搜索邮件"), ("read", "读取规则中匹配邮件的正文预览")):
        item = actions.add_parser(name, help=help_text)
        item.add_argument("--rule", required=True, help="相对于工作区的 JSON 规则文件")
        item.add_argument("--limit", type=int, default=50)
        item.add_argument("--output", default="outputs/mail-results.json")
        if name == "read":
            item.add_argument("--uid", help="只保留指定 UID")
            item.add_argument("--full-body", action="store_true", help="输出完整纯文本正文，而非摘要")
    download_parser = actions.add_parser("download", help="预览或下载规则匹配附件")
    download_parser.add_argument("--rule", required=True)
    download_parser.add_argument("--output", default="downloads")
    download_parser.add_argument("--allow-external-output", action="store_true")
    download_parser.add_argument("--confirm-download", action="store_true")
    download_parser.add_argument("--limit", type=int, default=200, help="最多处理的匹配邮件数，必须为正整数")
    job_parser = actions.add_parser("run-job", help="运行一次规则任务，只报告新匹配邮件")
    job_parser.add_argument("--job", required=True, help="相对于工作区的任务 JSON 文件")
    actions.add_parser("check-storage", help="只检查全部任务工作区的临时容量，不连接邮箱或写入文件")
    return main


def write_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def write_result_file(path: Path, value: object) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        fail(f"无法写入结果文件：{path}（{exc.strerror or exc}）")


def audit(workspace: Path, args, operation: str, inputs: dict, status: str, result: dict | None = None, error: str | None = None) -> None:
    try:
        write_audit(workspace, operation=operation, function=f"app/scripts/mail.py {args.action}", user_request=args.request_note, status=status, inputs=inputs, result=result, error=error)
    except OSError:
        pass


def main() -> None:
    args = parser().parse_args()
    workspace = None
    try:
        workspace = workspace_root(Path.cwd())
        storage = inspect_workspace_storage(skill_root(Path(__file__).resolve()), workspace)
        if args.action == "check-storage":
            write_json(storage)
            return
        if storage["状态"] == "超出阈值":
            write_json(storage)
            return
        config = load_config(Path(__file__))
        if args.action == "send":
            result = send(config, args, workspace)
            result["工作区容量检查"] = storage
            audit(workspace, args, "发送邮件", {"收件人": result["to"], "抄送人数": len(result["cc"]), "密送人数": result["bcc_count"], "主题": result["subject"], "纯文本长度": len(args.text), "HTML长度": len(args.html or ""), "附件": result["attachments"]}, "预览" if result["status"] == "preview" else "已提交", {"结果状态": result["status"], "邮件标识": result.get("message_id", "")})
            write_json(result)
            return
        if args.action in ("search", "read"):
            items = search(config, workspace, args.rule, args.limit, include_body=args.action == "read", full_body=args.action == "read" and args.full_body)
            if args.action == "read" and args.uid:
                items = [item for item in items if item["uid"] == args.uid]
            destination = safe_child(workspace, workspace / args.output)
            write_result_file(destination, {"messages": items})
            audit(workspace, args, "搜索邮件" if args.action == "search" else "读取邮件", {"规则": args.rule, "最大数量": args.limit, "指定UID": getattr(args, "uid", "") or "", "读取完整正文": bool(getattr(args, "full_body", False))}, "成功", {"匹配数量": len(items), "结果文件": str(destination.relative_to(workspace))})
            write_json({"count": len(items), "output": str(destination), "工作区容量检查": storage})
            return
        if args.action == "download":
            result = download(config, workspace, args.rule, workspace / args.output, args.allow_external_output, args.confirm_download, args.limit)
            state = "downloaded" if args.confirm_download else "preview"
            record = workspace / "outputs" / "download-record.json"
            write_result_file(record, {"status": state, "items": result})
            audit(workspace, args, "下载附件", {"规则": args.rule, "目标目录": args.output, "工作区外目录": args.allow_external_output, "确认下载": args.confirm_download, "最大数量": args.limit}, "预览" if state == "preview" else "成功", {"附件数量": len(result["items"]), "选择范围": result["选择范围"], "记录文件": "outputs/download-record.json"})
            write_json({"status": state, "items": result, "record": str(record), "工作区容量检查": storage})
            return
        job_path = safe_child(workspace, workspace / args.job)
        job = load_json(job_path)
        rule = job.get("rule")
        if not isinstance(rule, str):
            fail("任务文件必须包含 rule 字符串。")
        state_path = safe_child(workspace, workspace / job.get("state_file", "outputs/job-state.json"))
        previous = load_json(state_path).get("uids", []) if state_path.exists() else []
        limit = job.get("limit", 50)
        items = search(config, workspace, rule, limit, include_body=False)
        new_items = [item for item in items if item["uid"] not in previous]
        write_result_file(state_path, {"uids": [item["uid"] for item in items]})
        output = save_result(workspace, "job-new-messages.json", new_items)
        audit(workspace, args, "检查新匹配邮件", {"任务文件": args.job, "规则": rule, "最大数量": limit}, "成功", {"新增数量": len(new_items), "结果文件": str(output.relative_to(workspace))})
        write_json({"new_count": len(new_items), "output": str(output), "工作区容量检查": storage})
    except ValueError as exc:
        if workspace is not None:
            audit(workspace, args, "操作失败", {"命令": args.action}, "失败", error=str(exc))
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

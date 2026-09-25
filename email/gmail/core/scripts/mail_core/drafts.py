"""Local, workspace-scoped email draft persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _fail(message: str) -> None:
    raise ValueError(message)


def _addresses(values: list[str] | None, label: str) -> list[str]:
    result: list[str] = []
    for value in values or []:
        for address in value.split(","):
            address = address.strip()
            if not address:
                continue
            if "\r" in address or "\n" in address or "@" not in address:
                _fail(f"{label}地址格式无效。")
            result.append(address)
    return result


def _inside(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("附件必须位于本次任务工作区内。") from exc
    return candidate


def create_draft(workspace: Path, args) -> dict:
    """Save a non-sending local draft under ``workspace/drafts``.

    Drafts are deliberately local JSON files.  They are not appended to a remote
    mailbox and cannot result in a message being sent.
    """
    workspace = workspace.resolve()
    recipients = _addresses(args.to, "收件人")
    if not recipients:
        _fail("至少需要一个收件人。")
    cc = _addresses(args.cc, "抄送")
    subject = args.subject or ""
    if "\r" in subject or "\n" in subject:
        _fail("主题不能包含换行符。")

    name = Path(args.name)
    if name.is_absolute() or name.name != str(name) or name.name in {"", ".", ".."}:
        _fail("草稿名称必须是单个文件名。")
    if name.suffix.lower() != ".json":
        name = name.with_suffix(".json")
    destination = workspace / "drafts" / name.name
    if destination.exists() and not args.overwrite:
        _fail("草稿已存在；如需覆盖，请显式传入 --overwrite。")

    attachments: list[str] = []
    for raw_path in args.attachment or []:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        candidate = _inside(workspace, candidate)
        if not candidate.is_file():
            _fail("草稿附件不存在或不是文件。")
        attachments.append(str(candidate.relative_to(workspace)))

    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "to": recipients,
        "cc": cc,
        "subject": subject,
        "text": args.text or "",
        "html": args.html,
        "attachments": attachments,
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "saved",
        "draft": str(destination.relative_to(workspace)),
        "recipient_count": len(recipients),
        "cc_count": len(cc),
        "attachment_count": len(attachments),
    }

from __future__ import annotations

import email
import imaplib
import json
import re
import ssl
from datetime import datetime, timezone
from email.header import decode_header
from email.policy import default
from html.parser import HTMLParser
from pathlib import Path

from .common import fail, load_json, safe_child
from .auth import imap_login
from .proxy import open_tls_socket


class ProxyIMAP4_SSL(imaplib.IMAP4_SSL):
    def open(self, host: str = "", port: int = imaplib.IMAP4_SSL_PORT, timeout=None) -> None:
        self.host = host
        self.port = port
        self.sock = open_tls_socket(host, port, timeout)
        self.file = self.sock.makefile("rb")

def require_positive_limit(value: object, label: str = "结果上限") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(f"{label}必须是正整数。")
    return value


def _imap_failure(exc: BaseException) -> None:
    if isinstance(exc, OSError):
        fail("IMAP 网络或连接失败。请检查网络、服务器地址和端口。")
    fail("IMAP 认证或协议失败。请检查客户端访问权限和本地凭据。")


def _header(value: str | None) -> str:
    if not value:
        return ""
    return "".join(part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part for part, charset in decode_header(value))


def _attachments(message) -> list[dict]:
    found = []
    for index, part in enumerate(message.walk()):
        name = _header(part.get_filename())
        if name or part.get_content_disposition() == "attachment":
            found.append({"part": index, "filename": name or f"attachment-{index}", "content_type": part.get_content_type(), "size": len(part.get_payload(decode=True) or b"")})
    return found


class _HtmlText(HTMLParser):
    """Produce a readable fallback for HTML-only messages without dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"style", "script", "head"}:
            self.ignored_depth += 1
            return
        if tag.lower() in {"br", "p", "div", "li", "tr", "hr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"style", "script", "head"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def _decode_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        value = part.get_content()
        return value if isinstance(value, str) else str(value)
    for charset in (part.get_content_charset(), "utf-8", "gb18030", "latin-1"):
        if charset:
            try:
                return payload.decode(charset, errors="replace")
            except LookupError:
                continue
    return payload.decode("utf-8", errors="replace")


def _body_parts(message, full_body: bool) -> list[dict]:
    """Return every non-attachment MIME body part; binary parts are metadata only."""
    result = []
    limit = None if full_body else 800
    for index, part in enumerate(message.walk()):
        if part.is_multipart() or part.get_content_disposition() == "attachment" or part.get_filename():
            continue
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True) or b""
        if content_type.startswith("text/"):
            content = _decode_text(part)
            record = {"part": index, "content_type": content_type, "content": content if limit is None else content[:limit]}
            if content_type == "text/html":
                parser = _HtmlText()
                parser.feed(content)
                readable = parser.text()
                record["plain_text"] = readable if limit is None else readable[:limit]
            result.append(record)
        elif part.get_content_disposition() == "inline" or content_type.startswith("image/"):
            result.append({"part": index, "content_type": content_type, "binary": True, "size": len(payload)})
    return result


def _readable_text(parts: list[dict], limit: int | None) -> str:
    plain = [part["content"] for part in parts if part["content_type"] == "text/plain"]
    html = [part.get("plain_text", "") for part in parts if part["content_type"] == "text/html"]
    value = "\n\n".join(plain or html).strip()
    return value if limit is None else value[:limit]


def _rule(workspace: Path, name: str) -> dict:
    path = Path(name)
    if not path.is_absolute():
        path = workspace / path
    return load_json(safe_child(workspace, path))


def _criteria(filters: dict) -> list[str]:
    criteria = ["UNSEEN"] if filters.get("unread") is True else ["ALL"]
    for key, imap_key in (("from", "FROM"), ("to", "TO"), ("subject", "SUBJECT"), ("since", "SINCE"), ("before", "BEFORE")):
        value = filters.get(key)
        if value:
            if not isinstance(value, str) or any(char in value for char in "\r\n\""):
                fail(f"规则 filters.{key} 无效。")
            criteria.extend([imap_key, value])
    return criteria


def _matches(item: dict, filters: dict) -> bool:
    def includes(field: str, needle: str) -> bool:
        return needle.lower() in item[field].lower()
    for field, target in (("from_contains", "from"), ("to_contains", "to"), ("subject_contains", "subject")):
        if filters.get(field) and not includes(target, str(filters[field])):
            return False
    attachments = item["attachments"]
    if filters.get("has_attachment") is True and not attachments:
        return False
    extension = filters.get("attachment_extension")
    if extension and not any(a["filename"].lower().endswith(str(extension).lower()) for a in attachments):
        return False
    name = filters.get("attachment_name_contains")
    if name and not any(str(name).lower() in a["filename"].lower() for a in attachments):
        return False
    return True


def search_with_metadata(config: dict, workspace: Path, rule_name: str, limit: int, include_body: bool = False, full_body: bool = False) -> tuple[list[dict], dict]:
    limit = require_positive_limit(limit)
    rule = _rule(workspace, rule_name)
    filters = rule.get("filters", {})
    if not isinstance(filters, dict):
        fail("规则 filters 必须是对象。")
    imap, account = config["imap"], config["account"]
    client = None
    try:
        client = ProxyIMAP4_SSL(imap["host"], int(imap["port"]), timeout=30)
        imap_login(client, config)
        status, _ = client.select(rule.get("mailbox", "INBOX"), readonly=True)
        if status != "OK":
            fail("无法打开指定邮箱目录。")
        status, data = client.uid("search", None, *_criteria(filters))
        if status != "OK":
            fail("IMAP 搜索失败。")
        all_uids = data[0].split()
        uids = all_uids[-limit:]
        result = []
        for raw_uid in reversed(uids):
            uid = raw_uid.decode()
            status, payload = client.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            message = email.message_from_bytes(payload[0][1], policy=default)
            item = {"uid": uid, "from": _header(message.get("From")), "to": _header(message.get("To")), "subject": _header(message.get("Subject")), "date": _header(message.get("Date")), "attachments": _attachments(message)}
            if include_body:
                parts = _body_parts(message, full_body)
                item["body_parts"] = parts
                item["text" if full_body else "text_preview"] = _readable_text(parts, None if full_body else 800)
            if _matches(item, filters):
                result.append(item)
        return result, {"候选总数": len(all_uids), "实际处理数": len(uids), "上限": limit, "是否截断": len(all_uids) > len(uids)}
    except (OSError, imaplib.IMAP4.error) as exc:
        _imap_failure(exc)
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def search(config: dict, workspace: Path, rule_name: str, limit: int, include_body: bool = False, full_body: bool = False) -> list[dict]:
    return search_with_metadata(config, workspace, rule_name, limit, include_body, full_body)[0]


def update_read_state(config: dict, mailbox: str, uids: list[str], mark_read: bool) -> dict:
    """Set or clear IMAP's Seen flag for explicit UIDs."""
    if not mailbox or any(character in mailbox for character in "\r\n"):
        fail("邮箱目录无效。")
    normalized = []
    for uid in uids:
        if not isinstance(uid, str) or not re.fullmatch(r"[1-9][0-9]*", uid):
            fail("UID 必须是正整数。")
        if uid not in normalized:
            normalized.append(uid)
    if not normalized:
        fail("至少需要一个 UID。")
    imap = config["imap"]
    client = None
    try:
        client = ProxyIMAP4_SSL(imap["host"], int(imap["port"]), timeout=30)
        imap_login(client, config)
        status, _ = client.select(mailbox, readonly=False)
        if status != "OK":
            fail("无法打开指定邮箱目录。")
        command = "+FLAGS.SILENT" if mark_read else "-FLAGS.SILENT"
        for uid in normalized:
            status, _ = client.uid("store", uid, command, r"(\Seen)")
            if status != "OK":
                fail("无法更新指定邮件的已读状态。")
        return {"mailbox": mailbox, "uids": normalized, "read": mark_read}
    except (OSError, imaplib.IMAP4.error) as exc:
        _imap_failure(exc)
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass

def save_result(workspace: Path, name: str, items: list[dict]) -> Path:
    destination = workspace / "outputs" / name
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "messages": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def download(config: dict, workspace: Path, rule_name: str, destination: Path, allow_external: bool, confirm: bool, limit: int) -> dict:
    destination = safe_child(workspace, destination, allow_external)
    items, selection = search_with_metadata(config, workspace, rule_name, limit, include_body=False)
    preview = [{"uid": item["uid"], "attachments": item["attachments"]} for item in items]
    if not confirm:
        return {"items": preview, "选择范围": selection}
    destination.mkdir(parents=True, exist_ok=True)
    rule = _rule(workspace, rule_name)
    imap, account = config["imap"], config["account"]
    client = None
    try:
        client = ProxyIMAP4_SSL(imap["host"], int(imap["port"]), timeout=30)
        imap_login(client, config)
        status, _ = client.select(rule.get("mailbox", "INBOX"), readonly=True)
        if status != "OK":
            fail("无法打开指定邮箱目录。")
        downloaded = []
        for item in items:
            status, payload = client.uid("fetch", item["uid"], "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            message = email.message_from_bytes(payload[0][1], policy=default)
            for attachment in _attachments(message):
                part = list(message.walk())[attachment["part"]]
                content = part.get_payload(decode=True) or b""
                filename = Path(attachment["filename"]).name
                path = destination / f"{item['uid']}_{filename}"
                if path.exists():
                    continue
                path.write_bytes(content)
                downloaded.append({"uid": item["uid"], "filename": filename, "path": str(path)})
        return {"items": downloaded, "选择范围": selection}
    except (OSError, imaplib.IMAP4.error) as exc:
        _imap_failure(exc)
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass



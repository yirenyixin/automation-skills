from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from .common import fail
from .auth import smtp_login
from .proxy import open_tls_socket


class ProxySMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        if self.debuglevel > 0:
            self._print_debug("connect:", (host, port))
        return open_tls_socket(host, port, timeout)

def _addresses(values: list[str], label: str) -> list[str]:
    result = [item.strip() for value in values for item in value.split(",") if item.strip()]
    if label == "收件人" and not result:
        fail("至少需要一个收件人。")
    if any("@" not in item or "\n" in item or "\r" in item for item in result):
        fail(f"{label} 包含无效邮箱地址。")
    return result


def send(config: dict, args, workspace: Path) -> dict:
    to, cc, bcc = _addresses(args.to, "收件人"), _addresses(args.cc, "抄送人"), _addresses(args.bcc, "密送人")
    if "\n" in args.subject or "\r" in args.subject:
        fail("主题不能包含换行符。")
    attachments = [Path(item) for item in args.attachment]
    for item in attachments:
        if not item.is_file():
            fail(f"附件不存在：{item}")
        if item.stat().st_size > args.max_attachment_mb * 1024 * 1024:
            fail(f"附件超过 {args.max_attachment_mb} MB：{item.name}")
    result = {"to": to, "cc": cc, "bcc_count": len(bcc), "subject": args.subject, "attachments": [x.name for x in attachments]}
    if not args.confirm_send:
        result["status"] = "preview"
        return result
    account, smtp = config["account"], config["smtp"]
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = account["email"], ", ".join(to), args.subject
    message["Message-ID"] = make_msgid(domain=account["email"].split("@", 1)[1])
    if cc:
        message["Cc"] = ", ".join(cc)
    message.set_content(args.text)
    if args.html:
        message.add_alternative(args.html, subtype="html")
    for item in attachments:
        mime, _ = mimetypes.guess_type(item.name)
        major, minor = (mime or "application/octet-stream").split("/", 1)
        message.add_attachment(item.read_bytes(), maintype=major, subtype=minor, filename=item.name)
    try:
        with ProxySMTP_SSL(smtp["host"], int(smtp["port"]), context=ssl.create_default_context(), timeout=args.timeout) as client:
            smtp_login(client, config)
            client.send_message(message, from_addr=account["email"], to_addrs=list(dict.fromkeys(to + cc + bcc)))
    except smtplib.SMTPRecipientsRefused:
        fail("SMTP 拒绝一个或多个收件人。请核对收件人地址或投递权限。")
    except smtplib.SMTPAuthenticationError:
        fail("Gmail SMTP 应用专用密码认证失败。请检查本地配置、两步验证和应用专用密码。")
    except smtplib.SMTPException:
        fail("Gmail SMTP 协议或服务器拒绝操作。请检查邮件内容、应用专用密码和服务权限。")
    except OSError:
        fail("SMTP 网络或连接失败。请检查网络、服务器地址和端口。")
    result.update({"status": "submitted", "message_id": message["Message-ID"]})
    return result




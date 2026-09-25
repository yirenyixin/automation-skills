"""Proxy-aware TLS sockets using the operating system and standard proxy settings."""

from __future__ import annotations

import base64
import socket
import ssl
from urllib.parse import unquote, urlparse
from urllib.request import getproxies, proxy_bypass

from .common import fail


def _proxy_url(host: str) -> str | None:
    if proxy_bypass(host):
        return None
    proxies = getproxies()
    return proxies.get("https") or proxies.get("http") or proxies.get("all")


def _connect_tunnel(proxy_url: str, host: str, port: int, timeout: float | None) -> socket.socket:
    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        fail("系统代理格式不受支持；仅支持 HTTP 或 HTTPS CONNECT 代理。")
    proxy_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    connection = socket.create_connection((parsed.hostname, proxy_port), timeout=timeout)
    if parsed.scheme == "https":
        connection = ssl.create_default_context().wrap_socket(connection, server_hostname=parsed.hostname)
    headers = [f"CONNECT {host}:{port} HTTP/1.1", f"Host: {host}:{port}", "Proxy-Connection: Keep-Alive"]
    if parsed.username:
        credentials = f"{unquote(parsed.username)}:{unquote(parsed.password or '')}".encode()
        headers.append("Proxy-Authorization: Basic " + base64.b64encode(credentials).decode())
    connection.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response and len(response) < 32_768:
        chunk = connection.recv(4096)
        if not chunk:
            break
        response += chunk
    status_line = response.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    if not status_line.startswith("HTTP/") or " 200 " not in status_line:
        connection.close()
        fail("系统代理未能建立到 Gmail 的 CONNECT 隧道。请检查代理权限和规则。")
    return connection


def open_tls_socket(host: str, port: int, timeout: float | None = None) -> socket.socket:
    """Open TLS to a mail server, automatically tunneling through the system proxy when present."""
    proxy_url = _proxy_url(host)
    raw = _connect_tunnel(proxy_url, host, port, timeout) if proxy_url else socket.create_connection((host, port), timeout=timeout)
    return ssl.create_default_context().wrap_socket(raw, server_hostname=host)

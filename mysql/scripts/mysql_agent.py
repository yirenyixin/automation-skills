#!/usr/bin/env python3
"""A deliberately small, script-enforced read-only MySQL CLI."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 200
HARD_MAX_LIMIT = 1000
DEFAULT_MAX_EXPORT_BYTES = 10 * 1024 * 1024
IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
FORBIDDEN_SQL = re.compile(
    r"\b(?:insert|update|delete|replace|merge|create|alter|drop|truncate|grant|revoke|"
    r"call|do|handler|procedure|load\s+data|into\s+(?:outfile|dumpfile)|load_file|lock\s+(?:tables|in\s+share\s+mode)|"
    r"for\s+(?:update|share)|set|prepare|execute|deallocate|transaction|commit|rollback)\b|@",
    re.IGNORECASE,
)


class CliError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code, self.message, self.retryable = code, message, retryable
        super().__init__(message)


def emit(ok: bool, data: Any = None, meta: dict[str, Any] | None = None, error: CliError | None = None) -> None:
    payload: dict[str, Any] = {"ok": ok, "data": data, "meta": meta or {}}
    payload["error"] = None if error is None else {"code": error.code, "message": error.message, "retryable": error.retryable}
    print(json.dumps(payload, ensure_ascii=False, default=str))


def sanitize_error(value: Exception | str) -> str:
    text = str(value)
    text = EMAIL.sub("[redacted-email]", text)
    text = re.sub(r"(?i)(password|token|secret)\s*[=:]?\s*[^\s,;]+", r"\1=[redacted]", text)
    text = re.sub(r"(?i)(host|server)\s*[=:]?\s*[^\s,;]+", r"\1=[redacted]", text)
    return text[:300] or "Database operation failed"


def positive_int(value: Any, name: str, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CliError("INVALID_ARGUMENT", f"{name} must be a positive integer") from exc
    if result < 1 or (maximum is not None and result > maximum):
        bound = f" no greater than {maximum}" if maximum else ""
        raise CliError("INVALID_ARGUMENT", f"{name} must be a positive integer{bound}")
    return result


def connection_config() -> dict[str, Any]:
    required = {key: os.getenv(key, "").strip() for key in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD")}
    if not all(required.values()):
        missing = [key for key, value in required.items() if not value]
        raise CliError("CONFIG_MISSING", "Missing required MySQL configuration: " + ", ".join(missing))
    port = positive_int(os.getenv("MYSQL_PORT", "3306"), "MYSQL_PORT", 65535)
    config = {"host": required["MYSQL_HOST"], "port": port, "user": required["MYSQL_USER"], "password": required["MYSQL_PASSWORD"]}
    database = os.getenv("MYSQL_DATABASE", "").strip()
    if database:
        validate_identifier(database, "database")
        config["database"] = database
    config["connection_timeout"] = positive_int(os.getenv("MYSQL_CONNECT_TIMEOUT", "5"), "MYSQL_CONNECT_TIMEOUT", 3600)
    config["read_timeout"] = positive_int(os.getenv("MYSQL_READ_TIMEOUT", "15"), "MYSQL_READ_TIMEOUT", 3600)
    return config


def config_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {"host": "[configured]", "port": config["port"], "user": "[configured]", "database": config.get("database"), "connection_timeout_seconds": config["connection_timeout"], "read_timeout_seconds": config["read_timeout"]}


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise CliError("INVALID_IDENTIFIER", f"{label} must contain only letters, digits, underscore, dollar sign")
    return value


def max_rows() -> int:
    return positive_int(os.getenv("MYSQL_MAX_ROWS", str(DEFAULT_LIMIT)), "MYSQL_MAX_ROWS", HARD_MAX_LIMIT)


def max_export_bytes() -> int:
    return positive_int(os.getenv("MYSQL_MAX_EXPORT_BYTES", str(DEFAULT_MAX_EXPORT_BYTES)), "MYSQL_MAX_EXPORT_BYTES")


def validate_read_only_sql(sql: str, limit: int) -> str:
    normalized = sql.strip()
    if not normalized:
        raise CliError("SQL_EMPTY", "SQL file is empty")
    if re.search(r"--|#|/\*|\*/", normalized):
        raise CliError("SQL_REJECTED", "SQL comments are not allowed")
    if ";" in normalized[:-1] or normalized.count(";") > 1:
        raise CliError("SQL_REJECTED", "Only one SQL statement is allowed")
    normalized = normalized.rstrip(";").rstrip()
    if not re.match(r"^(?:select\b|with\b)", normalized, re.IGNORECASE) or FORBIDDEN_SQL.search(normalized):
        raise CliError("SQL_REJECTED", "Only a single non-locking SELECT query is allowed")
    if normalized.lower().startswith("with") and not re.search(r"\bselect\b", normalized, re.IGNORECASE):
        raise CliError("SQL_REJECTED", "WITH queries must produce a SELECT result")
    match = re.search(r"\blimit\s+(\d+)(?:\s*,\s*(\d+)|\s+offset\s+(\d+))?\s*$", normalized, re.IGNORECASE)
    if re.search(r"\blimit\b", normalized, re.IGNORECASE) and not match:
        raise CliError("SQL_REJECTED", "LIMIT must be a literal final clause")
    if match:
        returned = int(match.group(2) or match.group(1))
        if returned > limit:
            raise CliError("LIMIT_EXCEEDED", f"SQL LIMIT exceeds the requested maximum of {limit}")
        return normalized
    return f"{normalized} LIMIT {limit}"


def load_sql_and_params(args: argparse.Namespace) -> tuple[str, Any]:
    try:
        sql = Path(args.sql_file).read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError("SQL_FILE_ERROR", "Unable to read SQL file") from exc
    params: Any = []
    if args.params_json:
        try:
            params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CliError("PARAMS_FILE_ERROR", "Unable to read a valid JSON parameter file") from exc
        if not isinstance(params, (list, dict)):
            raise CliError("PARAMS_INVALID", "Parameters must be a JSON array or object")
    return sql, params


def driver_connect(config: dict[str, Any]):
    try:
        import mysql.connector  # type: ignore
    except ImportError as exc:
        raise CliError("DRIVER_MISSING", "Install dependencies from scripts/requirements.txt") from exc
    try:
        return mysql.connector.connect(**config)
    except Exception as exc:
        raise CliError("CONNECTION_FAILED", sanitize_error(exc), retryable=True) from exc


def execute(config: dict[str, Any], sql: str, params: Any) -> tuple[list[str], list[tuple[Any, ...]], float]:
    started = time.monotonic()
    connection = driver_connect(config)
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        columns = [item[0] for item in (cursor.description or [])]
        return columns, rows, round((time.monotonic() - started) * 1000, 2)
    except CliError:
        raise
    except Exception as exc:
        raise CliError("QUERY_FAILED", sanitize_error(exc), retryable=False) from exc
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def audit(path: str | None, operation: str, sql: str | None, status: str, elapsed_ms: float, error: CliError | None = None) -> None:
    if not path:
        return
    record = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "operation_id": hashlib.sha256(f"{time.time_ns()}:{operation}".encode()).hexdigest()[:16], "operation": operation, "execution_mode": "read_only", "sql_fingerprint": hashlib.sha256((sql or "").encode()).hexdigest() if sql else None, "status": status, "elapsed_ms": elapsed_ms, "error_code": error.code if error else None}
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise CliError("AUDIT_WRITE_FAILED", "Unable to write audit log") from exc


def cmd_config(_: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    config = connection_config()
    return config_summary(config), {}


def cmd_ping(_: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    config = connection_config()
    cols, rows, elapsed = execute(config, "SELECT VERSION() AS version, CURRENT_USER() AS current_user, DATABASE() AS current_database", [])
    return dict(zip(cols, rows[0])) if rows else {}, {"elapsed_ms": elapsed}


def cmd_list_databases(_: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    config = connection_config()
    cols, rows, elapsed = execute(config, "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name", [])
    return [dict(zip(cols, row)) for row in rows], {"elapsed_ms": elapsed}


def cmd_list_tables(args: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    config = connection_config()
    database = validate_identifier(args.database or config.get("database", ""), "database")
    sql = "SELECT table_name, table_type, table_rows FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name"
    cols, rows, elapsed = execute(config, sql, [database])
    return [dict(zip(cols, row)) for row in rows], {"database": database, "elapsed_ms": elapsed}


def cmd_describe(args: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    config = connection_config()
    database, table = validate_identifier(args.database or config.get("database", ""), "database"), validate_identifier(args.table, "table")
    sql = "SELECT column_name, column_type, is_nullable, column_default, column_key, extra FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position"
    cols, rows, elapsed = execute(config, sql, [database, table])
    return [dict(zip(cols, row)) for row in rows], {"database": database, "table": table, "elapsed_ms": elapsed}


def cmd_query(args: argparse.Namespace, explain: bool = False) -> tuple[Any, dict[str, Any]]:
    raw_sql, params = load_sql_and_params(args)
    configured_max = max_rows()
    limit = configured_max if args.limit is None else positive_int(args.limit, "limit", configured_max)
    sql = validate_read_only_sql(raw_sql, limit)
    args._audit_sql = sql
    config = connection_config()
    run_sql = f"EXPLAIN FORMAT=JSON {sql}" if explain else sql
    cols, rows, elapsed = execute(config, run_sql, params)
    data = [dict(zip(cols, row)) for row in rows]
    return data, {"elapsed_ms": elapsed, "limit": limit, "truncated": len(data) >= limit, "sql_fingerprint": hashlib.sha256(sql.encode()).hexdigest()}


def cmd_export(args: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    data, meta = cmd_query(args)
    output = Path(args.output)
    if output.exists():
        raise CliError("OUTPUT_EXISTS", "Refusing to overwrite an existing export")
    if args.format == "jsonl":
        content = "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in data)
        if len(content.encode("utf-8")) > max_export_bytes():
            raise CliError("EXPORT_TOO_LARGE", "Export exceeds MYSQL_MAX_EXPORT_BYTES")
        output.write_text(content, encoding="utf-8")
    else:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(data[0]) if data else [])
        if data:
            writer.writeheader(); writer.writerows(data)
        content = buffer.getvalue()
        if len(content.encode("utf-8")) > max_export_bytes():
            raise CliError("EXPORT_TOO_LARGE", "Export exceeds MYSQL_MAX_EXPORT_BYTES")
        with output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]) if data else [])
            if data:
                writer.writeheader(); writer.writerows(data)
    return {"path": str(output), "rows": len(data)}, meta


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Safe read-only MySQL client")
    root.add_argument("--audit-log")
    sub = root.add_subparsers(dest="command", required=True)
    config = sub.add_parser("config"); config_sub = config.add_subparsers(dest="config_command", required=True); config_sub.add_parser("validate")
    sub.add_parser("ping"); sub.add_parser("list-databases")
    for name in ("list-tables", "describe-table"):
        item = sub.add_parser(name); item.add_argument("--database");
        if name == "describe-table": item.add_argument("--table", required=True)
    for name in ("query", "explain", "export"):
        item = sub.add_parser(name); item.add_argument("--sql-file", required=True); item.add_argument("--params-json"); item.add_argument("--limit", type=int)
        if name == "export": item.add_argument("--format", choices=("csv", "jsonl"), required=True); item.add_argument("--output", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    started, error = time.monotonic(), None
    try:
        if args.command == "config": data, meta = cmd_config(args)
        elif args.command == "ping": data, meta = cmd_ping(args)
        elif args.command == "list-databases": data, meta = cmd_list_databases(args)
        elif args.command == "list-tables": data, meta = cmd_list_tables(args)
        elif args.command == "describe-table": data, meta = cmd_describe(args)
        elif args.command == "query": data, meta = cmd_query(args)
        elif args.command == "explain": data, meta = cmd_query(args, explain=True)
        else: data, meta = cmd_export(args)
        audit(args.audit_log, args.command, getattr(args, "_audit_sql", None), "success", round((time.monotonic() - started) * 1000, 2)); emit(True, data, meta); return 0
    except CliError as exc:
        error = exc
        try:
            audit(getattr(args, "audit_log", None), getattr(args, "command", "unknown"), getattr(args, "_audit_sql", None), "failed", round((time.monotonic() - started) * 1000, 2), exc)
        except CliError:
            pass
        emit(False, None, {}, exc); return 2
    except Exception:
        error = CliError("INTERNAL_ERROR", "Unexpected local failure")
        emit(False, None, {}, error); return 3


if __name__ == "__main__":
    sys.exit(main())

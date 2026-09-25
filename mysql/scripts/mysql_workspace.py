"""Isolated workspace, confirmation, and controlled-write helpers for mysql_agent."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DANGEROUS = re.compile(r"\b(grant|revoke|create\s+user|alter\s+user|drop\s+user|truncate|drop\s+(?:database|table|view|procedure|function|trigger))\b", re.I)
DDL = re.compile(r"^\s*(create|alter|drop|rename|truncate)\b", re.I)
DML_HIGH = re.compile(r"^\s*(update|delete)\b", re.I)
DML = re.compile(r"^\s*(insert|replace|update|delete)\b", re.I)
SELECT = re.compile(r"^\s*(select|with|show|describe|explain)\b", re.I)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)


def workspace_root(value: str | None) -> Path:
    root = Path(value or os.getcwd()).resolve()
    path = root / ".mysql-agent"
    (path / "runs").mkdir(parents=True, exist_ok=True)
    (path / "changes").mkdir(parents=True, exist_ok=True)
    (path / "approvals").mkdir(parents=True, exist_ok=True)
    return path


def git_metadata(root: Path) -> dict[str, Any]:
    try:
        base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
        return {"available": True, "base_revision": base, "branch": branch or None}
    except (OSError, subprocess.CalledProcessError):
        return {"available": False, "base_revision": None, "branch": None}


def init_workspace(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(args.workspace_dir or os.getcwd()).resolve()
    state = workspace_root(str(root)) / "workspace.json"
    payload = {"created_at": _now(), "root": str(root), "git": git_metadata(root), "purpose": "isolated MySQL agent artifacts"}
    if not state.exists():
        state.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json.loads(state.read_text(encoding="utf-8")), {}


def workspace_status(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(args.workspace_dir or os.getcwd()).resolve()
    state = workspace_root(str(root)) / "workspace.json"
    payload = json.loads(state.read_text(encoding="utf-8")) if state.exists() else None
    return {"root": str(root), "initialized": payload is not None, "workspace": payload, "git": git_metadata(root)}, {}



def workspace_snapshot(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(args.workspace_dir or os.getcwd()).resolve()
    metadata = git_metadata(root)
    if not metadata["available"]:
        raise ValueError("Git is unavailable in this workspace; initialize or select a Git worktree before taking a version snapshot")
    status = subprocess.run(["git", "-C", str(root), "status", "--short"], text=True, capture_output=True, check=True).stdout.splitlines()
    diff = subprocess.run(["git", "-C", str(root), "diff", "--no-ext-diff", "--binary"], text=True, capture_output=True, check=True).stdout
    record = {"timestamp": _now(), "message": args.message or None, "git": metadata, "changed_paths": status, "diff_fingerprint": _digest(diff)}
    path = workspace_root(str(root)) / "workspace-snapshots.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"snapshot_file": str(path), **record}, {}
def classify(sql: str) -> str:
    if DANGEROUS.search(sql):
        return "extreme"
    if DML_HIGH.match(sql) or re.match(r"^\s*alter\b", sql, re.I):
        return "high"
    if DML.match(sql) or DDL.match(sql):
        return "medium"
    if SELECT.match(sql):
        return "low"
    return "extreme"


def _copy_inputs(base: Path, sql: str, params: Any) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / "statement.sql").write_text(sql, encoding="utf-8")
    (base / "params.json").write_text(json.dumps(params, ensure_ascii=False, default=str, indent=2) + "\n", encoding="utf-8")


def _read_inputs(args: Any) -> tuple[str, Any]:
    sql = Path(args.sql_file).read_text(encoding="utf-8")
    params: Any = []
    if getattr(args, "params_json", None):
        params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
        if not isinstance(params, (list, dict)):
            raise ValueError("Parameters must be a JSON array or object")
    return sql, params


def _record(root: Path, run_id: str, record: dict[str, Any]) -> None:
    with (root / "runs" / f"{run_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def preview(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    sql, params = _read_inputs(args)
    level, run_id = classify(sql), _run_id()
    root = workspace_root(getattr(args, "workspace_dir", None))
    change = root / "changes" / run_id
    _copy_inputs(change, sql, params)
    token = secrets.token_urlsafe(24) if level in {"high", "extreme"} else None
    approval = {"run_id": run_id, "created_at": _now(), "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "pending", "risk_level": level, "sql_fingerprint": _digest(sql), "parameters_fingerprint": _digest(json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)), "database": os.getenv("MYSQL_DATABASE") or None, "confirmation_id": token}
    (root / "approvals" / f"{run_id}.json").write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _record(root, run_id, {"timestamp": _now(), "run_id": run_id, "operation": "preview", "risk_level": level, "status": "success", "sql_fingerprint": approval["sql_fingerprint"], "parameters_fingerprint": approval["parameters_fingerprint"]})
    strategy = "transaction rollback before commit" if level in {"medium", "high"} else "not required"
    if level in {"high", "extreme"}:
        strategy = "explicit rollback SQL is required before a committed execution; some DDL may require a backup or manual recovery"
    return {"run_id": run_id, "risk_level": level, "confirmation_required": token is not None, "confirmation_id": token, "expires_at": approval["expires_at"], "rollback_strategy": strategy, "artifacts": str(change)}, {}


def _approval(root: Path, run_id: str, token: str, sql: str, params: Any) -> dict[str, Any]:
    path = root / "approvals" / f"{run_id}.json"
    if not path.exists():
        raise ValueError("Preview approval record was not found")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value["status"] != "pending" or value.get("confirmation_id") != token:
        raise ValueError("Confirmation token is invalid or already used")
    if value["sql_fingerprint"] != _digest(sql) or value["parameters_fingerprint"] != _digest(json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)):
        raise ValueError("SQL or parameters differ from the approved preview")
    if datetime.now(timezone.utc) >= datetime.strptime(value["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc):
        raise ValueError("Confirmation token has expired")
    return value


def controlled_execute(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    sql, params = _read_inputs(args)
    root = workspace_root(getattr(args, "workspace_dir", None))
    level = classify(sql)
    if DML_HIGH.match(sql) and not re.search(r"\bwhere\b", sql, re.I):
        raise ValueError("UPDATE and DELETE require a WHERE clause")
    if level == "low":
        raise ValueError("Use query for read-only SQL")
    run_id = args.run_id
    if not run_id:
        raise ValueError("A preview run_id is required")
    approval = _approval(root, run_id, args.confirm or "", sql, params) if level in {"high", "extreme"} else None
    if level == "extreme" and not getattr(args, "backup_file", None):
        raise ValueError("Extreme risk operations require an existing --backup-file")
    if level in {"high", "extreme"} and not args.rollback_sql_file:
        raise ValueError("High and extreme risk operations require --rollback-sql-file")
    if level in {"high", "extreme"} and not args.commit:
        raise ValueError("High and extreme risk operations require explicit --commit")
    change = root / "changes" / run_id
    _copy_inputs(change, sql, params)
    if getattr(args, "backup_file", None):
        backup = Path(args.backup_file)
        if not backup.is_file():
            raise ValueError("--backup-file must reference an existing backup artifact")
        (change / "backup-reference.json").write_text(json.dumps({"path": str(backup.resolve()), "sha256": _digest(backup.read_text(encoding="utf-8", errors="replace"))}, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.rollback_sql_file:
        rollback = Path(args.rollback_sql_file).read_text(encoding="utf-8")
        (change / "rollback.sql").write_text(rollback, encoding="utf-8")
    started = time.monotonic()
    connection = None
    try:
        import mysql.connector
        required = {key: os.getenv(key, "").strip() for key in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD")}
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError("Missing required MySQL configuration: " + ", ".join(missing))
        kwargs = {"host": required["MYSQL_HOST"], "user": required["MYSQL_USER"], "password": required["MYSQL_PASSWORD"], "port": int(os.getenv("MYSQL_PORT", "3306")), "connection_timeout": int(os.getenv("MYSQL_CONNECT_TIMEOUT", "5")), "read_timeout": int(os.getenv("MYSQL_READ_TIMEOUT", "15"))}
        if os.getenv("MYSQL_DATABASE"):
            kwargs["database"] = os.environ["MYSQL_DATABASE"]
        connection = mysql.connector.connect(**kwargs)
        connection.start_transaction()
        cursor = connection.cursor()
        cursor.execute(sql, params)
        affected = cursor.rowcount
        lastrowid = cursor.lastrowid
        if args.commit:
            connection.commit(); status = "committed"
        else:
            connection.rollback(); status = "rolled_back"
        cursor.close()
        record = {"timestamp": _now(), "run_id": run_id, "operation": "execute", "risk_level": level, "status": status, "sql_fingerprint": _digest(sql), "affected_rows": affected, "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "rollback_artifact": str(change / "rollback.sql") if args.rollback_sql_file else None}
        _record(root, run_id, record)
        if approval:
            approval["status"] = "used"; (root / "approvals" / f"{run_id}.json").write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"run_id": run_id, "transaction": status, "affected_rows": affected, "lastrowid": lastrowid, "rollback_artifact": record["rollback_artifact"]}, {"elapsed_ms": record["elapsed_ms"], "risk_level": level}
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        _record(root, run_id, {"timestamp": _now(), "run_id": run_id, "operation": "execute", "risk_level": level, "status": "failed_rolled_back", "sql_fingerprint": _digest(sql), "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "error": str(exc)[:200]})
        raise
    finally:
        if connection is not None:
            connection.close()


def rollback_info(args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    root = workspace_root(getattr(args, "workspace_dir", None))
    path = root / "changes" / args.run_id / "rollback.sql"
    if not path.exists():
        return {"run_id": args.run_id, "available": False, "code": "ROLLBACK_UNAVAILABLE", "message": "No rollback SQL was archived for this run"}, {}
    return {"run_id": args.run_id, "available": True, "rollback_sql_file": str(path), "message": "Review this artifact, run preview on it, and obtain a new confirmation before execution."}, {}
"""持久记录本地模型任务的状态、检查点和可诊断原因。"""
from __future__ import annotations
import argparse, json, os, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path

STATES = {"running", "waiting_user", "blocked", "failed", "complete", "interrupted", "cancelled"}
ERROR_KINDS = {"none", "command_error", "tool_error", "permission_denied", "timeout", "dependency_missing", "validation_failed", "context_risk", "user_input_required", "external_interrupt", "unknown"}

def utc_now(): return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".status-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally: Path(temporary).unlink(missing_ok=True)

def load_run(run):
    run = run.resolve(); status_path = run / "status.json"
    if not status_path.is_file(): raise ValueError(f"运行目录缺少 status.json：{run}")
    return status_path, json.loads(status_path.read_text(encoding="utf-8"))

def append_event(run, status):
    keys = ("updated_at", "state", "phase", "reason", "next_action", "error_kind", "exit_code")
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({key: status.get(key) for key in keys}, ensure_ascii=False) + "\n"); stream.flush(); os.fsync(stream.fileno())

def update_run(run, *, state, phase=None, reason=None, next_action=None, error_kind=None, exit_code=None):
    if state not in STATES: raise ValueError(f"无效状态：{state}")
    if error_kind is not None and error_kind not in ERROR_KINDS: raise ValueError(f"无效错误类别：{error_kind}")
    status_path, status = load_run(run); status["state"] = state; status["updated_at"] = utc_now()
    for key, value in (("phase", phase), ("reason", reason), ("next_action", next_action), ("error_kind", error_kind), ("exit_code", exit_code)):
        if value is not None: status[key] = value
    if state == "complete": status["completed_at"] = status["updated_at"]
    atomic_json(status_path, status); append_event(status_path.parent, status); return status

def init_command(args):
    root = args.root.resolve(); root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex[:8]; run = root / run_id; run.mkdir(); now = utc_now()
    status = {"schema_version": 1, "run_id": run_id, "task": args.task, "state": "running", "phase": "初始化", "reason": "任务已启动", "next_action": "进入第一个执行阶段", "error_kind": "none", "exit_code": None, "started_at": now, "updated_at": now}
    atomic_json(run / "status.json", status); append_event(run, status); print(run)

def update_command(args):
    status = update_run(args.run, state=args.state, phase=args.phase, reason=args.reason, next_action=args.next_action, error_kind=args.error_kind, exit_code=args.exit_code)
    print(json.dumps(status, ensure_ascii=False, indent=2))

def show_command(args):
    _, status = load_run(args.run); print(json.dumps(status, ensure_ascii=False, indent=2))

def diagnose_command(args):
    _, status = load_run(args.run); updated = datetime.fromisoformat(status["updated_at"]); age = max(0, int((datetime.now(timezone.utc) - updated).total_seconds())); state = status["state"]
    if state == "running" and age >= args.stale_seconds:
        diagnosis = "运行状态已过期；疑似模型、宿主、工具进程或系统在最后检查点后中断，无法仅凭状态文件确认是否为上下文限制。"; certainty = "推断"
    elif state == "failed": diagnosis = f"已记录执行失败，错误类别为 {status.get('error_kind', 'unknown')}。"; certainty = "已确认"
    elif state == "waiting_user": diagnosis = "任务正在等待用户输入、确认或权限。"; certainty = "已确认"
    elif state == "complete": diagnosis = "任务已正常完成。"; certainty = "已确认"
    else: diagnosis = f"当前状态为 {state}，最后更新时间距今 {age} 秒。"; certainty = "状态记录"
    print(json.dumps({"certainty": certainty, "diagnosis": diagnosis, "age_seconds": age, "status": status}, ensure_ascii=False, indent=2))

def parser():
    root = argparse.ArgumentParser(description=__doc__); sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--task", required=True); init.add_argument("--root", type=Path, default=Path(".agent-runs")); init.set_defaults(function=init_command)
    update = sub.add_parser("update"); update.add_argument("run", type=Path); update.add_argument("--state", required=True, choices=sorted(STATES)); update.add_argument("--phase"); update.add_argument("--reason"); update.add_argument("--next-action"); update.add_argument("--error-kind", choices=sorted(ERROR_KINDS)); update.add_argument("--exit-code", type=int); update.set_defaults(function=update_command)
    show = sub.add_parser("show"); show.add_argument("run", type=Path); show.set_defaults(function=show_command)
    diagnose = sub.add_parser("diagnose"); diagnose.add_argument("run", type=Path); diagnose.add_argument("--stale-seconds", type=int, default=300); diagnose.set_defaults(function=diagnose_command)
    return root

def main():
    args = parser().parse_args()
    try: args.function(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc: raise SystemExit(f"状态操作失败：{exc}") from exc
if __name__ == "__main__": main()

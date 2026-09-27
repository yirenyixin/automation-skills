"""执行命令并把开始、退出码、超时或中断写入运行状态。"""
from __future__ import annotations
import argparse, subprocess
from pathlib import Path
from run_status import update_run

def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--run", required=True, type=Path); parser.add_argument("--phase", required=True); parser.add_argument("--next-action", default="检查命令结果"); parser.add_argument("--timeout", type=float); parser.add_argument("command", nargs=argparse.REMAINDER); args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command: parser.error("缺少要执行的命令")
    update_run(args.run, state="running", phase=args.phase, reason="命令开始执行", next_action=args.next_action, error_kind="none")
    try: result = subprocess.run(command, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        update_run(args.run, state="failed", phase=args.phase, reason="命令执行超时", next_action="检查超时设置或拆分任务", error_kind="timeout"); raise SystemExit(124)
    except FileNotFoundError:
        update_run(args.run, state="failed", phase=args.phase, reason="命令或依赖不存在", next_action="检查依赖与 PATH", error_kind="dependency_missing"); raise SystemExit(127)
    except KeyboardInterrupt:
        update_run(args.run, state="interrupted", phase=args.phase, reason="收到键盘中断", next_action="确认是否继续", error_kind="external_interrupt"); raise SystemExit(130)
    if result.returncode:
        update_run(args.run, state="failed", phase=args.phase, reason=f"命令以退出码 {result.returncode} 结束", next_action="检查命令输出并修复后重试", error_kind="command_error", exit_code=result.returncode)
    else:
        update_run(args.run, state="running", phase=args.phase, reason="命令执行成功", next_action=args.next_action, error_kind="none", exit_code=0)
    raise SystemExit(result.returncode)
if __name__ == "__main__": main()

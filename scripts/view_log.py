#!/usr/bin/env python3
"""
로그 뷰어: logs/agent_YYYYMMDD.jsonl 파싱해서 출력

사용법:
    python scripts/view_log.py                              # 오늘 전체 로그
    python scripts/view_log.py --task test-dms-files-view_files-00
    python scripts/view_log.py --event browser_use_step
    python scripts/view_log.py --task <id> --event browser_use_step
    python scripts/view_log.py --date 20260430
    python scripts/view_log.py --steps                      # browser_use_step만
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import date

# 출력 컬러 (터미널 지원 시)
_C = {
    "RESET": "\033[0m",
    "GRAY":  "\033[90m",
    "CYAN":  "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW":"\033[93m",
    "RED":   "\033[91m",
    "BOLD":  "\033[1m",
}

_LEVEL_COLOR = {
    "INFO":    _C["CYAN"],
    "WARNING": _C["YELLOW"],
    "ERROR":   _C["RED"],
    "DEBUG":   _C["GRAY"],
}

def _color(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"{code}{text}{_C['RESET']}"
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="employee-agent 로그 뷰어")
    parser.add_argument("--task", "-t",  help="run_task_id 필터 (부분 매칭)")
    parser.add_argument("--event", "-e", help="event 필터 (예: browser_use_step)")
    parser.add_argument("--steps", "-s", action="store_true", help="browser_use_step 이벤트만 표시")
    parser.add_argument("--date", "-d",  default=date.today().strftime("%Y%m%d"),
                        help="날짜 (YYYYMMDD, 기본: 오늘)")
    parser.add_argument("--log-dir",     default="C:/Users/seclab/Desktop/ZTAgent/test-data/logs",
                        help="로그 디렉토리")
    args = parser.parse_args()

    if args.steps:
        args.event = "browser_use_step"

    log_path = Path(args.log_dir) / f"agent_{args.date}.jsonl"
    if not log_path.exists():
        print(f"로그 파일 없음: {log_path}")
        sys.exit(1)

    count = 0
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 필터 적용
            task_id = rec.get("run_task_id", "")
            if args.task and args.task not in task_id:
                continue
            if args.event and rec.get("event") != args.event:
                continue

            # 출력 조립
            ts    = rec.get("timestamp", "")[:19]
            level = rec.get("level", "?").upper()
            event = rec.get("event", "")
            step  = rec.get("step", "")

            extra = {
                k: v for k, v in rec.items()
                if k not in ("timestamp", "level", "event", "run_task_id", "step")
            }

            level_str = _color(f"[{level:<4}]", _LEVEL_COLOR.get(level, ""))
            ts_str    = _color(ts, _C["GRAY"])
            event_str = _color(event, _C["BOLD"])

            parts = [f"{ts_str} {level_str} {event_str}"]
            if task_id:
                parts.append(_color(f"task={task_id}", _C["GREEN"]))
            if step != "":
                parts.append(f"step={step}")
            if extra:
                parts.append(json.dumps(extra, ensure_ascii=False)[:300])

            print("  ".join(parts))
            count += 1

    print(_color(f"\n─── {count}개 ───", _C["GRAY"]))


if __name__ == "__main__":
    main()

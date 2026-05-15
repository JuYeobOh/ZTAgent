"""컨테이너 자원 상태 스냅샷 — cgroup v2/v1 자동 감지.

호스트 자원 부족(RAM/swap/cgroup OOM/CPU throttle)으로 인한 work 실패를 사후
추적하기 위해 task 시작·실패·세션 재생성 시점에 jsonl에 찍는다.
표준 라이브러리만 사용, 모든 읽기 실패는 silently swallow 후 빈 dict 반환.
"""
from __future__ import annotations

from pathlib import Path


def _read_int(path: Path) -> int | None:
    try:
        v = path.read_text().strip()
        if v in ("", "max"):
            return None
        return int(v)
    except (OSError, ValueError):
        return None


def _read_kv(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    out[parts[0].rstrip(":")] = int(parts[1])
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def _meminfo() -> dict[str, int]:
    raw = _read_kv(Path("/proc/meminfo"))
    keys = ("MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree", "Buffers", "Cached")
    return {k: raw[k] * 1024 for k in keys if k in raw}


def _self_rss_bytes() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def _cgroup_v2() -> dict:
    base = Path("/sys/fs/cgroup")
    if not (base / "cgroup.controllers").exists():
        return {}
    cpu_stat = _read_kv(base / "cpu.stat")
    mem_events = _read_kv(base / "memory.events")
    return {
        "cg_mem_current": _read_int(base / "memory.current"),
        "cg_mem_peak": _read_int(base / "memory.peak"),
        "cg_mem_max": _read_int(base / "memory.max"),
        "cg_cpu_usage_usec": cpu_stat.get("usage_usec"),
        "cg_cpu_throttled_usec": cpu_stat.get("throttled_usec"),
        "cg_cpu_nr_throttled": cpu_stat.get("nr_throttled"),
        "cg_oom": mem_events.get("oom"),
        "cg_oom_kill": mem_events.get("oom_kill"),
    }


def _cgroup_v1() -> dict:
    base = Path("/sys/fs/cgroup/memory")
    if not base.exists():
        return {}
    return {
        "cg_mem_current": _read_int(base / "memory.usage_in_bytes"),
        "cg_mem_max": _read_int(base / "memory.limit_in_bytes"),
        "cg_oom_kill": _read_kv(base / "memory.oom_control").get("oom_kill"),
    }


def _chrome_procs() -> dict:
    """컨테이너 내 chrome/chromium 프로세스의 합산 RSS와 개수."""
    total_rss = 0
    n = 0
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip().lower()
            except OSError:
                continue
            if "chrome" not in comm and "chromium" not in comm:
                continue
            rss_kb = _read_kv(entry / "status").get("VmRSS")
            if rss_kb:
                total_rss += rss_kb * 1024
                n += 1
    except OSError:
        pass
    return {"chrome_rss_total": total_rss, "chrome_procs": n}


def snapshot() -> dict:
    """현재 컨테이너 자원 스냅샷. 절대 throw하지 않음."""
    snap: dict = {}
    try:
        mem = _meminfo()
        if mem:
            snap["host_mem_total"] = mem.get("MemTotal")
            snap["host_mem_available"] = mem.get("MemAvailable")
            snap["host_swap_total"] = mem.get("SwapTotal")
            snap["host_swap_free"] = mem.get("SwapFree")
        rss = _self_rss_bytes()
        if rss is not None:
            snap["agent_rss"] = rss
        cg = _cgroup_v2() or _cgroup_v1()
        snap.update({k: v for k, v in cg.items() if v is not None})
        snap.update(_chrome_procs())
    except Exception:
        pass
    return snap

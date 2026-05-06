#!/usr/bin/env python3
"""
diversity_audit.py — trace 파일들에서 첫 의미행동 분포의 Shannon entropy와 max_freq 계산.

Usage:
    python tools/diversity_audit.py <trace_dir>
    python tools/diversity_audit.py --demo  # 랜덤 데이터로 데모
"""
import sys
import json
import math
import random
from pathlib import Path
from collections import Counter


def compute_entropy(actions: list[str]) -> tuple[float, float]:
    """Shannon entropy (bits)와 max_freq 반환"""
    if not actions:
        return 0.0, 0.0
    counts = Counter(actions)
    total = len(actions)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    max_freq = max(counts.values()) / total
    return entropy, max_freq


def load_first_actions_from_traces(trace_dir: Path) -> list[str]:
    """trace JSON 파일들에서 첫 번째 의미행동 텍스트 추출"""
    actions = []
    for f in sorted(trace_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # browser-use history 형식: {"history": [{"action": {...}}, ...]}
            history = data.get("history", [])
            if history:
                first = history[0]
                action = first.get("action", {})
                # action은 dict {"click_element": {...}} 형태
                action_type = next(iter(action), "unknown")
                actions.append(action_type)
        except Exception as e:
            print(f"  [skip] {f.name}: {e}", file=sys.stderr)
    return actions


def demo_mode() -> None:
    """랜덤 데이터로 entropy 데모"""
    print("=== DEMO MODE (simulated traces) ===")
    actions = random.choices(
        ["click_element", "go_to_url", "input_text", "scroll_down", "click_element"],
        weights=[3, 2, 2, 1, 3],
        k=30,
    )
    entropy, max_freq = compute_entropy(actions)
    counts = Counter(actions)
    print(f"Sample size  : {len(actions)}")
    print(f"Action counts: {dict(counts)}")
    print(f"Shannon entropy: {entropy:.4f} bits  (threshold: log2(3) = {math.log2(3):.4f})")
    print(f"Max frequency  : {max_freq:.2%}  (threshold: < 70%)")
    print()
    if entropy >= math.log2(3) and max_freq < 0.70:
        print("✓ PASS: Diversity invariant satisfied")
    else:
        print("✗ FAIL: Diversity invariant NOT satisfied")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] == "--demo":
        demo_mode()
        return

    trace_dir = Path(sys.argv[1])
    if not trace_dir.is_dir():
        print(f"Error: {trace_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    actions = load_first_actions_from_traces(trace_dir)
    if not actions:
        print("No trace files found.", file=sys.stderr)
        sys.exit(1)

    entropy, max_freq = compute_entropy(actions)
    counts = Counter(actions)

    print(f"Trace directory: {trace_dir}")
    print(f"Sample size    : {len(actions)}")
    print(f"Action counts  : {dict(counts)}")
    print(f"Shannon entropy: {entropy:.4f} bits  (threshold >= {math.log2(3):.4f})")
    print(f"Max frequency  : {max_freq:.2%}  (threshold < 70%)")
    print()
    passed = entropy >= math.log2(3) and max_freq < 0.70
    print("✓ PASS" if passed else "✗ FAIL", ": Diversity invariant")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

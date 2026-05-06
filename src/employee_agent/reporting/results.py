from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaskResult:
    screenshots_path: str | None
    browser_trace_path: str | None
    metadata: dict = field(default_factory=dict)  # {"steps": int, "final_url": str | None}


def package_result(
    history: object,
    results_dir: str,
    run_task_id: str,
    trace_dir: Path | None = None,
) -> TaskResult:
    """browser-use AgentHistoryList에서 TaskResult를 패키징.

    history가 None이거나 속성이 없으면 빈 결과 반환.
    history.screenshots() -> List[str] 경로 목록 (있으면 첫 번째를 screenshots_path로)
    history.model_actions() -> 실행된 action 목록 (len -> steps)
    history 마지막 url은 history.urls()[-1] 또는 None
    trace_dir이 있으면 해당 디렉터리에서 *.zip을 우선 탐색.
    """
    if history is None:
        return TaskResult(
            screenshots_path=None,
            browser_trace_path=None,
            metadata={"steps": 0, "final_url": None},
        )

    # screenshots
    screenshots_path: str | None = None
    try:
        shots = history.screenshots()  # type: ignore[attr-defined]
        if shots:
            screenshots_path = shots[0]
    except (AttributeError, TypeError):
        pass

    # steps from model_actions
    steps = 0
    try:
        actions = history.model_actions()  # type: ignore[attr-defined]
        steps = len(actions)
    except (AttributeError, TypeError):
        pass

    # final url
    final_url: str | None = None
    try:
        urls = history.urls()  # type: ignore[attr-defined]
        if urls:
            final_url = urls[-1]
    except (AttributeError, TypeError):
        pass

    # browser trace path — try known browser-use / Playwright attribute names
    browser_trace_path: str | None = None
    for attr in ("trace_path", "browser_trace_path"):
        try:
            val = getattr(history, attr, None)
            if callable(val):
                val = val()
            if val:
                browser_trace_path = str(val)
                break
        except Exception:
            pass

    # fallback: glob for *.zip — prefer trace_dir (BrowserSession writes there)
    if browser_trace_path is None:
        if trace_dir is not None:
            candidates = list(trace_dir.glob("*.zip"))
            if candidates:
                browser_trace_path = str(candidates[0])
        else:
            import glob as _glob
            candidates_str = _glob.glob(f"{results_dir}/{run_task_id}*.zip")
            if candidates_str:
                browser_trace_path = candidates_str[0]

    # browser_use Agent 자체 성공 판정
    is_successful: bool = True
    try:
        is_successful = bool(history.is_successful())  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass

    final_result_text: str | None = None
    try:
        final_result_text = history.final_result()  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass

    return TaskResult(
        screenshots_path=screenshots_path,
        browser_trace_path=browser_trace_path,
        metadata={
            "steps": steps,
            "final_url": final_url,
            "is_successful": is_successful,
            "final_result": final_result_text,
        },
    )

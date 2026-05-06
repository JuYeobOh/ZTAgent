import random
from pathlib import Path
from employee_agent.sites.base import SiteHandler, SiteRegistry

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "dms_system.md"

# ── 전체 직원 ID 목록 (groupoffice.py와 동일) ─────────────────────────────
_ALL_EMPLOYEES: list[str] = [
    "branch-dev-director",  "branch-dev-manager",   "branch-dev-senior",    "branch-dev-staff",
    "branch-it-director",   "branch-it-manager",    "branch-it-senior",     "branch-it-staff",
    "enter-fin-director",   "enter-fin-manager",    "enter-fin-senior",     "enter-fin-staff",
    "enter-hr-director",    "enter-hr-manager",     "enter-hr-senior",      "enter-hr-staff",
    "enter-sales-director", "enter-sales-manager",  "enter-sales-senior",   "enter-sales-staff",
]

# ── 부서별 DMS 업무 컨텍스트 ──────────────────────────────────────────────
_DEPT_CONTEXT: dict[str, str] = {
    "hr":    "You work in the HR department. Your DMS files include personnel records, recruitment documents, onboarding materials, and company policy files.",
    "dev":   "You work in the Development department. Your DMS files include code artifacts, sprint planning docs, technical specifications, and review notes.",
    "fin":   "You work in the Finance department. Your DMS files include budget spreadsheets, expense reports, financial statements, and compliance records.",
    "sales": "You work in the Sales department. Your DMS files include client proposals, sales reports, meeting notes, and customer correspondence.",
    "it":    "You work in the IT department. Your DMS files include system configuration docs, maintenance logs, asset inventories, and security policies.",
}

# ── 역할별 DMS 행동 컨텍스트 ─────────────────────────────────────────────
_ROLE_CONTEXT: dict[str, str] = {
    "staff":    "As Staff, you mainly manage your own files in '개인 파일' and occasionally access your department's Team folder.",
    "senior":   "As Senior Staff, you actively use both '개인 파일' and your department's Team folder to share knowledge with junior members.",
    "manager":  "As Manager, you frequently upload and organize documents in Team folders and review files shared by your team.",
    "director": "As Director, you primarily review high-level documents in Team folders and occasionally upload strategic documents.",
}


def _to_display(employee_id: str) -> str:
    """EMPLOYEE_ID → 표시 이름 (e.g. 'enter-hr-staff' → 'hr staff')"""
    parts = employee_id.split("-")
    return " ".join(parts[1:]) if len(parts) >= 3 else employee_id


def _parse_employee(employee_id: str) -> tuple[str, str]:
    """EMPLOYEE_ID → (dept, role_key)"""
    parts = employee_id.split("-")
    if len(parts) >= 3:
        dept = parts[1]
        role_raw = "-".join(parts[2:]).rstrip("0123456789")
        return dept, role_raw
    return "unknown", "staff"


def _get_folder_nav(cfg=None) -> str:
    """파일/폴더 생성 위치: 개인 파일 or 팀 폴더(부서/director) 중 랜덤 선택.
    반환값은 템플릿에 직접 삽입되는 자연어 안내 문자열.
    Role 폴더는 'director'만 존재 — 본인이 director일 때만 옵션에 포함.
    """
    employee_id = getattr(cfg, "EMPLOYEE_ID", None) if cfg else None
    options = ["your personal folder (click '개인 파일' in the left sidebar)"]
    if employee_id:
        dept, role = _parse_employee(employee_id)
        options.append(
            f"the '{dept}' team folder (click 'Team folders' in the left sidebar, then open the '{dept}' folder)"
        )
        if role == "director":
            options.append(
                "the 'director' team folder (click 'Team folders' in the left sidebar, then open the 'director' folder)"
            )
    return random.choice(options)


def _get_share_targets(cfg=None) -> list[str]:
    """공유 대상 목록: 특정 직원 표시 이름 + 부서명 + 직급명 중 혼합"""
    self_id = getattr(cfg, "EMPLOYEE_ID", None) if cfg else None
    employees = [_to_display(e) for e in _ALL_EMPLOYEES if e != self_id]
    depts = ["hr", "dev", "fin", "sales", "it"]
    roles = ["director", "manager", "senior", "staff"]
    return employees + depts + roles


_ACTION_TEMPLATES: dict[str, dict] = {

    "files.view_files": {
        "templates": [
            "Click '모든 파일' in the DMS left navigation. Done as soon as the file list is visible — report done immediately.",
            "Click '개인 파일' in the left sidebar of DMS to browse personal files. Done when the file list loads.",
            "In DMS, click '모든 파일' from the left nav and scroll through a few files. Done as soon as the list is visible.",
        ],
        "max_steps": 5,
    },

    "files.view_recent": {
        "templates": [
            "Click '최근' in the DMS left navigation. Done as soon as the recent files list appears — report done immediately.",
            "Navigate to the '최근' section by clicking it in the left sidebar. Done when the list loads.",
            "In DMS, select '최근' from the left nav to see recently modified files. Done as soon as the list is visible.",
        ],
        "max_steps": 5,
    },

    "files.view_favorites": {
        "templates": [
            "Click '즐겨찾기' in the DMS left navigation. Done as soon as the favorites list appears — report done immediately.",
            "Navigate to '즐겨찾기' by clicking it in the left sidebar. Done when the list loads.",
            "In DMS, select '즐겨찾기' from the left nav to see starred files. Done as soon as the panel is visible.",
        ],
        "max_steps": 5,
    },

    "files.browse_directory": {
        "templates": [
            "In DMS, click '모든 파일' in the left navigation. From the listed folders, click into one folder to view its contents, then go back (breadcrumb or '모든 파일') and open another folder. Repeat for 2–3 different folders one at a time. Done after browsing into at least 2 folders. If no folders exist, report done.",
            "Click '개인 파일' in the DMS left sidebar. Open folders one by one — click a folder to enter, look at its contents, return to the parent, then click the next folder. Visit 2–3 folders sequentially. Done when at least 2 folders have been opened. If the directory has no folders, report done.",
            "In DMS '모든 파일', browse the directory tree by clicking folders one at a time. Enter a folder, observe the file list, navigate back, and click into a different folder. Do this for 2–3 folders sequentially (not in parallel). Done after a few folders have been visited. If empty, report done.",
        ],
        "max_steps": 15,
    },

    "files.upload_file": {
        "templates": [
            "In DMS, navigate to {folder_nav}. IMPORTANT: you must actually click into that folder so you are inside it (the breadcrumb/title shows the folder name and its contents are listed) BEFORE creating the file — do not stay on the parent listing. Once inside the folder, click '새로 만들기' in the top toolbar and choose '새 텍스트 파일'. A template selection dialog appears — select '{file_template}' from the options (여백, Meeting notes, Product plan, Readme). Name the file '{filename}' and confirm to create it. The file opens in the text editor. Type free-form body content reflecting your department and role (e.g. tasks you handle, ongoing work, team responsibilities) — make up plausible content; do not leave the body empty. Then click the save button (저장) to persist the changes. Done after the body is written and saved.",
            "Navigate to {folder_nav} in DMS and click into that folder so you are browsing inside it (its contents are visible, not just the sidebar entry highlighted). Only after entering the folder, click the '새로 만들기' button and select '새 텍스트 파일'. When the template dialog appears, choose '{file_template}'. Enter '{filename}' as the filename and confirm. The text editor opens — write free-form content related to your job role and department (anything plausible: today's notes, work items, observations). After writing, click the save button (저장) to commit. Done once the content is saved.",
            "In DMS, navigate to {folder_nav}. First, click the folder so you are INSIDE it (the file list of that folder is shown). Then click '새로 만들기' → '새 텍스트 파일'. From the template options (여백, Meeting notes, Product plan, Readme), select '{file_template}'. Set the filename to '{filename}' and confirm. The editor opens — fill the body with made-up but plausible text matching your department and role (responsibilities, ongoing tasks, etc.). Then click the save button (저장) to save. Done when the body content is saved.",
        ],
        "params": {
            "filename": ["메모", "보고서초안", "회의록", "작업목록"],
            "file_template": ["여백", "Meeting notes", "Product plan", "Readme"],
        },
        "max_steps": 18,
    },

    "files.create_folder": {
        "templates": [
            "In DMS, navigate to {folder_nav}. Click into that folder so you are inside it (its contents are visible) before creating anything. Then click '새로 만들기' in the top toolbar and choose '새 폴더'. Enter '{foldername}' and confirm. Done when the folder appears in the list.",
            "Navigate to {folder_nav} in DMS and click into the folder to enter it (file list of that folder is shown). Once inside, click '새로 만들기', select '새 폴더', type '{foldername}' and press enter. Done when created.",
            "In DMS, navigate to {folder_nav}. First open the folder by clicking on it so you are browsing INSIDE it. Then click the '새로 만들기' button, select '새 폴더', enter '{foldername}' and save. Done when the folder is visible.",
        ],
        "params": {"foldername": ["임시폴더", "작업자료", "공유문서", "보고서"]},
        "max_steps": 10,
    },

    "files.rename_file": {
        "templates": [
            "In DMS '모든 파일', find any file in the list. Right-click it or click the '···' icon to open the context menu (which shows: 즐겨찾기에 추가, 자세한 정보, 이름 바꾸기, 이동이나 복사, 다운로드, 폴더에서 보기). Choose '이름 바꾸기'. Enter '{newname}' and confirm. Done when the file shows the new name. If no files exist, report done.",
            "Navigate to DMS '개인 파일'. Find a file, right-click or click the '···' icon to open the context menu, then select '이름 바꾸기'. Type '{newname}' and save. Done when renamed. If no files are available, report done.",
            "Go to DMS '모든 파일'. Hover over a file and click the '···' icon. From the context menu (includes 즐겨찾기에 추가, 이름 바꾸기, 이동이나 복사, 다운로드, etc.), choose '이름 바꾸기'. Type '{newname}' and confirm. Done when the name changes. If the directory is empty, report done.",
        ],
        "params": {"newname": ["업데이트_문서", "수정_보고서", "최종본", "검토완료"]},
        "max_steps": 10,
    },

    "files.move_file": {
        "templates": [
            "In DMS '모든 파일', find any file. Right-click it or click the '···' icon to open the context menu (which shows: 즐겨찾기에 추가, 자세한 정보, 이름 바꾸기, 이동이나 복사, 다운로드, 폴더에서 보기). Choose '이동이나 복사'. Select or create destination folder '{foldername}'. Confirm. Done when the file is moved. If no files exist, report done.",
            "Navigate to DMS '개인 파일'. Find a file, right-click or click '···', then select '이동이나 복사' from the context menu. Choose the target folder '{foldername}' (or create it). Confirm. Done when moved. If no files are available, report done.",
            "Go to DMS '모든 파일'. Right-click a file or click the '···' icon, then select '이동이나 복사' from the context menu (which includes 즐겨찾기에 추가, 이름 바꾸기, 이동이나 복사, 다운로드, etc.). Pick or create folder '{foldername}' as destination and confirm. Done when the file is moved. If empty, report done.",
        ],
        "params": {"foldername": ["임시폴더", "작업자료", "보관함", "보고서"]},
        "max_steps": 12,
    },

    "files.team_folder_browse": {
        "templates": [
            "In DMS, click 'Team folders' in the left navigation sidebar. You will see department folders (dev, hr, fin, sales, it) and a single role folder ('director' — no other role folders exist). Click into any folder to browse it. Done as soon as the folder's contents are visible — report done immediately. If 'Team folders' is not found, report done.",
            "Navigate to DMS and click 'Team folders' in the left sidebar. Browse the available folders — department folders (dev/hr/fin/sales/it) plus the 'director' role folder. Click into any folder to see its contents. Done when the folder list loads. If not available, report done.",
            "In DMS left navigation, click 'Team folders' to access shared group folders. The folders include department (dev, hr, fin, sales, it) and one role folder ('director'). Click any folder. Done the moment contents are visible. If not present, report done.",
        ],
        "max_steps": 6,
    },

    "files.team_folder_create": {
        "templates": [
            "In DMS, click 'Team folders' in the left navigation. Navigate into any department folder (or the 'director' folder if present). Click '새로 만들기' and create a new folder called '{foldername}'. Done when the folder is created. If Team folders is not available, report done.",
            "Go to DMS and click 'Team folders' in the sidebar. Enter a dept folder (dev, hr, fin, sales, it) or the 'director' role folder. Use '새로 만들기' → '새 폴더' to create a folder named '{foldername}'. Confirm. Done when visible. If not available, report done.",
            "In DMS, navigate to 'Team folders' in the sidebar and click into a team folder (department folders or 'director'). Click the new folder button and name it '{foldername}'. Done when created. If the section does not exist, report done.",
        ],
        "params": {"foldername": ["팀_공유", "프로젝트자료", "공통문서", "부서자료"]},
        "max_steps": 10,
    },

    "sharing.share_file": {
        "templates": [
            "In DMS '모든 파일', hover over any file and click the '공유 옵션' button (the share icon — do NOT use the '···' context menu). A sharing panel opens. Under the '내부 공유' section, type '{share_target}' in the search box. Wait for suggestions to appear and click on a matching result to add them as a collaborator. Done when sharing is set. If no files exist, report done.",
            "Go to DMS Files and hover over any file. Click the '공유 옵션' share icon directly (not the '···' menu). In the sharing panel that opens, find the '내부 공유' section and its search field. Type '{share_target}', wait for suggestions, and click on a matching user or group to share with. Done when they are added. If no files exist, report done.",
            "In DMS, hover over any file and click the '공유 옵션' button (share icon, not '···'). The sharing dialog opens. Under '내부 공유', use the search box to type '{share_target}'. Click on a result from the dropdown to add them as a collaborator. Done when sharing is confirmed. If no files are available, report done.",
        ],
        "max_steps": 12,
    },

    "search.search_files": {
        "templates": [
            "Click the '통합검색' button at the top of DMS and search for '{query}'. When results appear, click on one of the results to open it. Done when a result has been clicked.",
            "Use the search icon in the DMS header to search for '{query}'. When results appear, click on the first or any result to open it. Done when a result is opened.",
            "In DMS, open the integrated search (통합검색) and type '{query}'. Wait for results to load, then click on any one result to navigate to it. Done when a result has been clicked.",
        ],
        "params": {"query": ["보고서", "회의", "메모", "2026", "Nextcloud"]},
        "max_steps": 8,
    },

    "common.search": {
        "templates": [
            "Click the '통합검색' button at the top of DMS and search for '{query}'. When results appear, click on one of the results to open it. Done when a result has been clicked.",
            "Use the search icon in the DMS header to search for '{query}'. When results appear, click on any result to open it. Done when a result is opened.",
            "In DMS, open 통합검색 and type '{query}'. Wait for results to load, then click on one of the results. Done when a result is clicked.",
        ],
        "params": {"query": ["보고서", "회의", "메모", "2026", "Nextcloud"]},
        "max_steps": 8,
    },
}


class DMSHandler(SiteHandler):
    def build_goal(self, module: str, action: str, task=None, cfg=None) -> str:
        key = f"{module}.{action}"
        entry = _ACTION_TEMPLATES.get(key)
        if entry is None:
            return f"In DMS, navigate to {module} and perform {action}."

        template = random.choice(entry["templates"])
        params = {k: random.choice(v) for k, v in entry.get("params", {}).items()}

        if "{folder_nav}" in template:
            params["folder_nav"] = _get_folder_nav(cfg)

        if "{share_target}" in template:
            targets = _get_share_targets(cfg)
            params["share_target"] = random.choice(targets) if targets else "hr staff"

        return template.format(**params)

    def system_prompt(self, cfg=None) -> str:
        base = (
            _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
            if _SYSTEM_PROMPT_PATH.exists()
            else _DEFAULT_SYSTEM_PROMPT
        )
        if cfg is None:
            return base

        employee_id = getattr(cfg, "EMPLOYEE_ID", None)
        if not employee_id:
            return base

        dept, role = _parse_employee(employee_id)
        dept_ctx = _DEPT_CONTEXT.get(dept, "")
        role_ctx = _ROLE_CONTEXT.get(role, _ROLE_CONTEXT["staff"])

        return base + f"\n\n## Your Role\n{dept_ctx}\n{role_ctx}"

    def max_steps(self, action: str) -> int:
        for key, entry in _ACTION_TEMPLATES.items():
            if key.endswith(f".{action}"):
                return entry.get("max_steps", 10)
        return 10


_DEFAULT_SYSTEM_PROMPT = """You are operating Nextcloud 33.0.2 at https://dms.kmuinfosec.click."""

_handler = DMSHandler()
SiteRegistry.register("dms", _handler)

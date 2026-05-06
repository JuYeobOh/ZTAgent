import random
from pathlib import Path
from employee_agent.sites.base import SiteHandler, SiteRegistry

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "groupoffice_system.md"

# ── 전체 직원 ID 목록 ─────────────────────────────────────────────────────
# 형식: {org}-{dept}-{role}   /   GroupOffice 표시 이름: "{dept} {role}"
_ALL_EMPLOYEES: list[str] = [
    "branch-dev-director",  "branch-dev-manager",   "branch-dev-senior",    "branch-dev-staff",
    "branch-it-director",   "branch-it-manager",    "branch-it-senior",     "branch-it-staff",
    "enter-fin-director",   "enter-fin-manager",    "enter-fin-senior",     "enter-fin-staff",
    "enter-hr-director",    "enter-hr-manager",     "enter-hr-senior",      "enter-hr-staff",
    "enter-sales-director", "enter-sales-manager",  "enter-sales-senior",   "enter-sales-staff",
]

# ── 부서별 업무 컨텍스트 ──────────────────────────────────────────────────
_DEPT_CONTEXT: dict[str, str] = {
    "hr":    "You work in the Human Resources (HR) department. Your daily work involves personnel records, recruitment documentation, employee onboarding/offboarding, and company policy files.",
    "dev":   "You work in the Development (Engineering) department. Your daily work involves software tasks, sprint planning, code review notes, and technical documentation.",
    "fin":   "You work in the Finance department. Your daily work involves budget tracking, expense reports, financial statements, and compliance records.",
    "sales": "You work in the Sales department. Your daily work involves client proposals, sales pipeline updates, meeting notes, and customer correspondence.",
    "it":    "You work in the IT department. Your daily work involves system maintenance, helpdesk requests, asset inventory, and security policy documentation.",
}

# ── 역할별 행동 컨텍스트 ──────────────────────────────────────────────────
_ROLE_CONTEXT: dict[str, str] = {
    "staff":    "Your role is Staff. You carry out day-to-day operational tasks, collaborate with your immediate team, and report progress to your manager.",
    "senior":   "Your role is Senior Staff. You handle complex tasks independently, mentor junior members, and often collaborate cross-team.",
    "manager":  "Your role is Manager. You oversee your team, review and approve documents, delegate tasks, and coordinate with other department heads.",
    "director": "Your role is Director. You set team priorities, review strategic plans, and make cross-department decisions.",
}


def _to_display(employee_id: str) -> str:
    """EMPLOYEE_ID → GroupOffice 표시 이름 (e.g. 'enter-hr-staff' → 'hr staff')"""
    parts = employee_id.split("-")
    return " ".join(parts[1:]) if len(parts) >= 3 else employee_id


def _parse_employee(employee_id: str) -> tuple[str, str]:
    """EMPLOYEE_ID → (dept, role_key)  e.g. 'enter-dev-staff2' → ('dev', 'staff')"""
    parts = employee_id.split("-")
    if len(parts) >= 3:
        dept = parts[1]
        role_raw = "-".join(parts[2:]).rstrip("0123456789")
        return dept, role_raw
    return "unknown", "staff"


def _get_targets(cfg=None) -> list[str]:
    """자신을 제외한 전체 직원의 GroupOffice 표시 이름 목록"""
    self_id = getattr(cfg, "EMPLOYEE_ID", None) if cfg else None
    return [_to_display(e) for e in _ALL_EMPLOYEES if e != self_id]


def _get_notebooks(cfg=None) -> list[str]:
    """현재 직원의 노트북 목록: 팀 노트북(부서명) + 개인 노트북(부서+역할)
    예: enter-dev-manager → ['dev', 'dev manager']
    """
    employee_id = getattr(cfg, "EMPLOYEE_ID", None) if cfg else None
    if not employee_id:
        return ["업무 노트", "개인 메모"]
    dept, _role = _parse_employee(employee_id)
    display = _to_display(employee_id)  # e.g. "dev manager"
    return [dept, display]


# ── action별 goal templates ───────────────────────────────────────────────
_ACTION_TEMPLATES: dict[str, dict] = {

    # ── 캘린더 ──────────────────────────────────────────────────────────
    "calendar.switch_view": {
        "templates": [
            "Click the 'Calendar' tab in the top navigation bar. In the calendar toolbar, click the '{view}' view button once. Done immediately after clicking — do not verify or click again.",
            "Navigate to Calendar via the top nav tab. Find the '{view}' button in the calendar toolbar and click it once. Report done immediately after the single click.",
            "Open the Calendar module by clicking its tab. Locate the '{view}' view option in the toolbar and click it. Task is complete the moment you click.",
        ],
        "params": {"view": ["Week", "Day", "Year", "List", "5 Days"]},
        "max_steps": 10,
    },

    "calendar.create_event": {
        "templates": [
            "Click the global '+' (Add) button in the top-right corner of Group-Office. Choose 'Event' from the dropdown. Fill in the event title '{title}' and set the date to tomorrow. If there is a participants or invite field, type '{target}' into it, wait for the autocomplete dropdown to appear, then click on the matching result to add them. Fill in any other available fields (location, description). Click the Save button. Done when the event is saved.",
            "Navigate to Calendar via the top nav. Click on tomorrow's date cell to open a new event form. Enter the title '{title}' and set the start time. If a participants field is available, type '{target}', wait for the suggestion list to appear, and click on the matching entry to add them as a participant. Fill in other fields (location, notes) if visible. Click the Save button. Done when the event appears in the calendar.",
            "Click the 'Calendar' tab, then click the add/new button in the toolbar. Fill in the event title '{title}' and set the date to tomorrow. In the participants field, type '{target}', wait for the autocomplete results to appear, and click on a result to select them. Fill in additional fields (location, notes) if available. Click the Save button. Done when the form is submitted.",
        ],
        "params": {"title": ["팀 회의", "스프린트 리뷰", "1:1 미팅", "주간 보고", "기술 검토", "업무 협의", "프로젝트 킥오프"]},
        "max_steps": 15,
    },

    "calendar.manage_category": {
        "templates": [
            "In Group-Office Calendar, look for a category management option — try right-clicking a calendar entry in the left panel or clicking a gear/settings icon near the calendar list. Add a category called '{category}'. Done when saved. If you cannot find the setting after 3 attempts, report done and finish.",
            "Open the Calendar module. Look for calendar preferences or category settings (gear icon, right-click menu on a calendar). Create a new category named '{category}'. Done when the category is created. If not available, report done.",
            "Click the 'Calendar' tab. Try to add a calendar category via the settings or context menu. Name it '{category}'. Done when visible. If the option is not found after a few attempts, report done.",
        ],
        "params": {"category": ["업무", "개인", "팀 일정", "외부 미팅", "교육"]},
        "max_steps": 15,
    },

    "calendar.assign_category": {
        "templates": [
            "Click the 'Calendar' tab in the top navigation bar. Once the calendar grid loads, calendar event blocks have offsetParent=null and cannot be clicked by index — execute JavaScript `const els=document.querySelectorAll('.allday'); els[Math.floor(Math.random()*els.length)].dispatchEvent(new MouseEvent('dblclick',{{bubbles:false}}))` to open the first event's edit form. In the event form, find the 'Category' or '카테고리' field and click it. If the dropdown has options, select any one, then click the event title field inside the form to close the dropdown (do NOT click outside the form), then click Save. If the dropdown is empty, press Escape and report done. If the JavaScript throws an error (no events), report done.",
            "Click the 'Calendar' tab in the top navigation bar. Wait for the calendar grid to load. Calendar event bars cannot be clicked by index due to offsetParent=null — use JavaScript `const els=document.querySelectorAll('.allday'); els[Math.floor(Math.random()*els.length)].dispatchEvent(new MouseEvent('dblclick',{{bubbles:false}}))` to click the first event and open its edit form. Locate the category field ('Category' or '카테고리') and click it. If categories are available, select any one, then click the event title field inside the form to close the dropdown (do NOT click outside the form), then click Save. If the dropdown is empty, press Escape and report done. If no events exist, report done.",
            "Click the 'Calendar' tab in the top navigation to enter the Calendar module. Calendar event blocks are not in the interactive element index — execute JavaScript `const els=document.querySelectorAll('.allday'); els[Math.floor(Math.random()*els.length)].dispatchEvent(new MouseEvent('dblclick',{{bubbles:false}}))` to click the first visible event. In the edit form that opens, find the category selector and click it. If the dropdown shows categories, pick any one, then press Escape or click the title field inside the form to close it, then click Save. If the dropdown is empty, press Escape and report done. If the script errors (no events), report done.",
        ],
        "params": {"category": ["업무", "개인", "팀 일정", "외부 미팅", "교육"]},
        "max_steps": 15,
    },

    # ── 주소록 ──────────────────────────────────────────────────────────
    "address_book.view_contacts": {
        "templates": [
            "Click the 'Address book' tab in the top navigation bar. Done as soon as the contact list panel is open — report done immediately.",
            "Navigate to Address book by clicking its tab in the nav bar. Task complete the moment the contacts panel appears.",
            "Open the Address book module via the navigation tabs. When the contact list is visible, report done and finish.",
        ],
        "max_steps": 4,
    },

    "address_book.search_contact": {
        "templates": [
            "Click the 'Address book' tab. In the Address book module, find and click the search (🔍) button or search icon in the toolbar to open the search input. Type '{name}' into the search field and press Enter or wait for results. Done when search results appear.",
            "Click the 'Address book' tab. Look for a search button or magnifying glass icon inside the Address book toolbar and click it to activate the search field. Enter '{name}' in the search input and submit. Done when the results list loads.",
            "Navigate to Address book via the top nav tab. Click the search icon or search button in the Address book toolbar to open the search field. Type '{name}' and press Enter. Done when results are visible.",
        ],
        "params": {"name": ["manager", "director", "senior", "staff", "hr", "dev", "finance", "sales"]},
        "max_steps": 10,
    },

    "address_book.add_contact": {
        "templates": [
            "Click the global '+' (Add) button in the top-right corner and choose 'Contact' from the dropdown. Fill in first name '{firstname}', last name '{lastname}', and email '{email}'. Save. Done when the contact is created.",
            "Click the 'Address book' tab. Inside the Address book module, click the '+' button in the module toolbar, then choose 'Contact' from the dropdown. Enter first name '{firstname}', last name '{lastname}', and email '{email}'. Save. Done when saved.",
            "Navigate to Address book via the top nav. Click the '+' button in the Address book toolbar and select 'Contact' from the dropdown. Fill in first name '{firstname}', last name '{lastname}', email '{email}'. Save. Done when the contact appears.",
        ],
        "params": {
            "firstname": ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"],
            "lastname":  ["민준", "서연", "도윤", "예은", "지훈", "수빈", "현우", "지아", "준서", "유진"],
            "email":     ["test@example.com", "contact@demo.org", "user@sample.net", "info@testco.kr", "hello@company.com"],
        },
        "max_steps": 15,
    },

    "address_book.add_organization": {
        "templates": [
            "Click the global '+' (Add) button in the top-right corner of Group-Office and choose 'Organization' or '회사'. Fill in the organization name '{orgname}', phone '{phone}', and any other available fields (address, email, website, fax). Save. Done when the organization is created.",
            "Navigate to Address book via the top nav. Click the add/new button and look for an 'Organization' or '회사' option. Enter the organization name '{orgname}', fill in phone '{phone}' and all other available fields. Save. Done when saved.",
            "Open the Address book module and use the new item button to add an organization. Set the name to '{orgname}', fill in the phone number '{phone}', address, email, and any other available fields. Save. Done when the organization appears in the list.",
        ],
        "params": {
            "orgname": ["(주)테스트기업", "데모코리아 주식회사", "샘플그룹", "테크솔루션(주)", "글로벌비즈니스"],
            "phone":   ["02-1234-5678", "031-555-0100", "02-9876-5432", "051-234-5678", "032-555-7777"],
        },
        "max_steps": 15,
    },

    "address_book.comment_contact": {
        "templates": [
            "Click the 'Address book' tab. Find any contact in the list (try searching for '{name}'). Click directly on the contact row to open its detail view — the comment input only appears after clicking the contact. In the detail view, find the comments section and type: '{comment}'. Save. Done when saved. If no contacts are found, report done and finish.",
            "Navigate to Address book. Search for '{name}' or browse the list. Click directly on a contact row to open the contact detail — you must click the contact first to see the comment field. Find the comment or note area in the detail panel and write: '{comment}'. Submit. Done when saved. If unavailable, report done.",
            "Open the Address book module and click directly on any contact in the list to open its detail view. The comment input only appears after the contact is opened by clicking on it. In the contact detail, find the comments input, type '{comment}', and save. Done when saved. If no contacts exist, report done.",
        ],
        "params": {
            "name":    ["manager", "director", "senior", "staff", "hr", "dev", "finance", "sales"],
            "comment": ["연락처 확인 완료.", "미팅 예정.", "업무 협조 요청 예정.", "정보 업데이트 필요."],
        },
        "max_steps": 15,
    },

    # ── 할일(Tasks) ──────────────────────────────────────────────────────
    "tasks.view_tasks": {
        "templates": [
            "Click the 'Tasks' tab in the top navigation bar. Done as soon as the Tasks panel is open — report done immediately.",
            "Navigate to Tasks by clicking its tab in the nav bar. Once the task list appears, report done immediately.",
            "Open the Tasks module by clicking 'Tasks' in the navigation. The moment the module is visible, report done and finish.",
        ],
        "max_steps": 4,
    },

    "tasks.create_or_update_task": {
        "templates": [
            "Click the global '+' button in the top-right corner and choose 'Task'. Fill in the title '{title}', set the start date to today, set the due date to a random date within the next 2 weeks, and fill in any other available fields (description, priority). Click the Save button. Done when the task appears in the list.",
            "Click the 'Tasks' tab, then click the add button in the toolbar to create a new task. Enter the title '{title}', set start date to today, set a due date 3–14 days from now, and fill in other available fields (description, priority). Click the Save button. Done when saved.",
            "Navigate to Tasks via the top nav. Use the new task button to create a task called '{title}'. Set start date to today's date, set due date to a random date in the coming 2 weeks, fill in description or priority if available. Click the Save button. Done when the task is visible in the panel.",
        ],
        "params": {"title": ["업무 보고서 작성", "자료 정리", "미팅 준비", "코드 리뷰", "문서 업데이트", "주간 보고 준비"]},
        "max_steps": 15,
    },

    "tasks.complete_task": {
        "templates": [
            "Click the 'Tasks' tab in the top navigation. In the task list, find any incomplete task and click the small circular checkbox on the LEFT side of the task row (next to the task title) to mark it complete. Do NOT click the sidebar checkboxes like 'Show completed', 'Mine', or 'Unassigned'. Done when the task is checked off. If there are no tasks, report done and finish.",
            "Navigate to Tasks via the top nav. In the task list grid, locate any task row and click the round circle checkbox on the far left of that row to complete the task. The sidebar has unrelated checkboxes ('Show completed', 'Mine', 'Unassigned') — do not click those. Done when the circular checkbox is checked. If no tasks exist, report done.",
            "Open the Tasks module. Find any task in the list and click the circular checkbox at the left edge of the task row to mark it as done. Avoid the square checkboxes in the left sidebar panel. Done when the task's circle checkbox is checked. If the task list is empty, report done and finish.",
        ],
        "max_steps": 8,
    },

    "tasks.comment_task": {
        "templates": [
            "Click the 'Tasks' tab. Find any task in the list and click its title to open the detail view. Look for a comments or notes section inside the task detail. Write: '{comment}'. Save. Done when saved. If no tasks exist or there is no comment field, report done and finish.",
            "Navigate to Tasks. Click on any task to open its details. Find the comment or note input area and type: '{comment}'. Submit. Done when the comment is saved. If no tasks are available, report done.",
            "Open the Tasks module and click on any task. In the detail panel, look for a comment input. Enter '{comment}' and submit. Done when submitted. If the task list is empty or no comment field exists, report done.",
        ],
        "params": {"comment": ["확인했습니다.", "진행 중입니다.", "내일까지 완료 예정입니다.", "검토 후 업데이트하겠습니다."]},
        "max_steps": 10,
    },

    "tasks.manage_category": {
        "templates": [
            "In Group-Office Tasks, look for category or list management — check the left sidebar for category options or a settings/gear icon. Add a new category called '{category}'. Done when saved. If the feature is not available after a few attempts, report done.",
            "Open the Tasks module. Try right-clicking the task list or clicking a settings option to find category management. Create a category called '{category}'. Done when created. If not found, report done.",
            "Click the 'Tasks' tab. Look for category or folder management in the left panel, toolbar, or context menu. Add a category named '{category}'. Done when visible. If unavailable, report done.",
        ],
        "params": {"category": ["업무", "개인", "긴급", "보류", "완료"]},
        "max_steps": 10,
    },

    "tasks.assign_category": {
        "templates": [
            "Click the 'Tasks' tab and find any existing task in the list. Click the task to open its detail view. Look for a 'Category' or '카테고리' field — click it and a dropdown will appear. Note: if the dropdown is empty, no categories have been created yet; create them via the task category management option first. Select '{category}' from the dropdown and click Save. Done when saved. If no tasks exist, report done and finish.",
            "Navigate to Tasks. Click on any task to open its detail view. Find the category field and click to open the dropdown. If empty (no categories created), note that categories must be created first via the Tasks settings. Otherwise select '{category}' and click Save. Done when saved. If no tasks exist, report done.",
            "Open the Tasks module and click any task. In the task detail, find the category or '카테고리' selector. Click it to reveal the dropdown (may be empty if no categories exist — create them first if needed). Select '{category}'. Click the Save button. Done when the task is saved with the assigned category. If no tasks are found, report done.",
        ],
        "params": {"category": ["업무", "개인", "긴급", "보류", "완료"]},
        "max_steps": 12,
    },

    # ── 노트 ────────────────────────────────────────────────────────────
    "notes.view_notes": {
        "templates": [
            "Click the '노트' tab in the top navigation bar. Done as soon as the notes panel is open — report done immediately.",
            "Navigate to the 노트 module by clicking its tab in the nav bar. Task complete the moment the panel appears.",
            "Open 노트 by clicking it in the navigation bar. Report done immediately when the notes list is visible.",
        ],
        "max_steps": 4,
    },

    "notes.create_note": {
        "templates": [
            "Click the global '+' button and choose '노트'. Enter the title '{title}' and write a few lines about your current work. In the notebook selector, choose '{notebook}' — this is your notebook based on your account (team or personal). Save. Done when the note is created.",
            "Click the '노트' tab, then click the add button in the toolbar to create a new note. Set the title to '{title}', write a brief body, and select '{notebook}' as the target notebook (your department team folder or your personal folder). Save. Done when saved.",
            "Navigate to 노트 via the top nav. Use the toolbar to create a new note called '{title}'. Select '{notebook}' as the notebook (look for your department name or your personal folder name). Write a short body and save. Done when the note appears in the list under that notebook.",
        ],
        "params": {"title": ["업무 메모", "회의 기록", "아이디어", "체크리스트", "진행 현황", "참고 사항"]},
        "max_steps": 15,
    },

    "notes.create_or_edit_note": {
        "templates": [
            "Click the global '+' button and choose '노트'. Enter the title '{title}' and write a brief body. Save. Done when saved.",
            "Click the '노트' tab and create a new note titled '{title}' using the toolbar add button. Write a short body and save. Done when the note is saved.",
            "Navigate to 노트 and use the new note button to create a note called '{title}'. Add a few lines and save. Done when saved.",
        ],
        "params": {"title": ["업무 메모", "회의 기록", "아이디어", "체크리스트"]},
        "max_steps": 15,
    },

    "notes.comment_note": {
        "templates": [
            "Click the '노트' tab. Find any note in the list and open it by clicking its title. Look for a comments section at the bottom or in the detail panel. Write: '{comment}'. Submit. Done when saved. If there are no notes or no comment field, report done and finish.",
            "Navigate to 노트, then click on any note to open its detail view. Find the comment input and enter: '{comment}'. Save. Done when the comment appears. If no notes exist, report done.",
            "Open the 노트 module and click any note. In the note detail, look for a comment or discussion area. Type '{comment}' and submit. Done when saved. If no notes are available, report done.",
        ],
        "params": {"comment": ["확인했습니다.", "내용 검토 완료.", "수정이 필요할 것 같습니다.", "공유 감사합니다."]},
        "max_steps": 15,
    },

    "notes.manage_notebook": {
        "templates": [
            "In Group-Office 노트, look for a way to create or manage notebooks — check the left sidebar for a category or notebook list, or look for a '+' icon there. Create a new notebook called '{notebook}'. Done when the notebook is created. If the feature is not found, report done.",
            "Open the 노트 module. Try clicking a '+' icon in the left sidebar or a notebook/folder management option. Add a notebook named '{notebook}'. Done when saved. If unavailable, report done.",
            "Click the '노트' tab and look for notebook or folder management in the left panel or toolbar. Create a notebook called '{notebook}'. Done when it appears in the sidebar. If not available, report done.",
        ],
        "params": {"notebook": ["업무 노트", "개인 메모", "프로젝트", "참고 자료", "회의록"]},
        "max_steps": 15,
    },

    # ── 북마크 ──────────────────────────────────────────────────────────
    "bookmarks.view_bookmarks": {
        "templates": [
            "Click the '북마크' tab in the top navigation bar. Done as soon as the bookmarks panel is visible — report done immediately.",
            "Navigate to 북마크 by clicking its tab in the navigation. Task is complete the moment the panel opens — report done and finish.",
            "Open the 북마크 module from the top nav. As soon as the bookmarks list is visible, report done immediately.",
        ],
        "max_steps": 4,
    },

    "bookmarks.create_bookmark": {
        "templates": [
            "Click the '북마크' tab. In the bookmarks panel, click the add/new button. Enter the name '{name}' and URL '{url}'. Save. Done when the bookmark is created.",
            "Navigate to 북마크 via the top nav. Find the new bookmark or '+' button and click it. Set the name to '{name}' and URL to '{url}'. Save. Done when saved.",
            "Open 북마크 from the navigation. Use the toolbar add button to create a bookmark called '{name}' with URL '{url}'. Done when it appears in the list.",
        ],
        "params": {
            "name": ["뉴스", "참고 사이트", "공식 문서", "팀 위키", "사내 포털"],
            "url":  ["https://news.ycombinator.com", "https://docs.python.org", "https://github.com", "https://stackoverflow.com"],
        },
        "max_steps": 15,
    },

    "bookmarks.manage_bookmark": {
        "templates": [
            "Click the '북마크' tab. Find any existing bookmark in the list and open it by clicking, or right-click to edit it. Done when the bookmark is opened or modified. If no bookmarks exist, report done and finish.",
            "Navigate to 북마크. Find a bookmark in the list and click to open it or use the context menu to edit. Done when any interaction with an existing bookmark is complete. If the list is empty, report done.",
            "Open the 북마크 module. Look for any bookmark in the panel. Click to open or use the context menu. Done when the action is taken. If no bookmarks are available, report done.",
        ],
        "max_steps": 15,
    },

}


class GroupOfficeHandler(SiteHandler):
    def build_goal(self, module: str, action: str, task=None, cfg=None) -> str:
        key = f"{module}.{action}"
        entry = _ACTION_TEMPLATES.get(key) or _ACTION_TEMPLATES.get(f"common.{action}")
        if entry is None:
            return f"Navigate to the {module} module in Group-Office and perform the {action} action."

        template = random.choice(entry["templates"])
        params = {k: random.choice(v) for k, v in entry.get("params", {}).items()}

        if "{target}" in template:
            targets = _get_targets(cfg)
            params["target"] = random.choice(targets) if targets else "팀원"

        if "{notebook}" in template:
            notebooks = _get_notebooks(cfg)
            params["notebook"] = random.choice(notebooks) if notebooks else "업무 노트"

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
                return entry.get("max_steps", 14)
        return 14


_DEFAULT_SYSTEM_PROMPT = """You are operating Group-Office 26.x at https://group.kmuinfosec.click."""

SiteRegistry.register("groupoffice", GroupOfficeHandler())

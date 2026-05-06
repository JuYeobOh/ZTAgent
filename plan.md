# Employee Agent — 개발 계획 및 진행 현황

마지막 업데이트: 2026-05-04

---

## 현재 세션 변경사항 (2026-05-04)

| # | 항목 | 상태 | 설명 |
|---|------|------|------|
| 1 | 요약 대시보드 삭제 | ✅ 완료 | `summary.view_summary` 액션 및 테스트 태스크 제거 |
| 2 | 캘린더 저장 버튼 안내 | ✅ 완료 | `calendar.create_event` 모든 템플릿에 "Click Save button" 명시 |
| 3 | 한번에 채우는 값 제한 해제 | ✅ 완료 | `add_contact` 등 폼에 가능한 모든 필드 채우도록 템플릿 수정 |
| 4 | 캘린더 카테고리 할당 액션 | ✅ 완료 | `calendar.assign_category` 추가 (5가지 카테고리: 업무/개인/팀 일정/외부 미팅/교육) |
| 5 | add_contact 경우의 수 확대 | ✅ 완료 | firstname 10개, lastname 10개, email 5개, phone 5개, company 5개 추가 |
| 6 | add_organization 추가 | ✅ 완료 | `address_book.add_organization` 액션 추가 |
| 7 | tasks 날짜/저장 버튼 수정 | ✅ 완료 | 시작일=오늘, 마감일=랜덤(2주 내), 저장 버튼 클릭 명시 |
| 8 | 태스크 카테고리 할당 액션 | ✅ 완료 | `tasks.assign_category` 추가 (5가지 카테고리: 업무/개인/긴급/보류/완료) |
| 9 | notes 노트북 계정 기반 선택 | ✅ 완료 | `_get_notebooks(cfg)` → 팀 노트북(부서명) + 개인 노트북(부서+역할) 중 랜덤 |
| 10 | bookmarks.manage_category 삭제 | ✅ 완료 | 액션 및 테스트 태스크 제거 |
| 11 | plan.md 생성 | ✅ 완료 | 이 파일 |

---

## GroupOffice 액션 목록 (현재)

| 모듈 | 액션 | 테스트 포함 | 비고 |
|------|------|------------|------|
| calendar | switch_view | ✅ | |
| calendar | create_event | ✅ | {target} 치환, 저장 버튼 명시 |
| calendar | manage_category | ✅ | 5가지 카테고리 생성 |
| calendar | assign_category | ✅ | 기존 이벤트에 카테고리 할당, 빈 드롭다운 안내 포함 |
| address_book | view_contacts | ✅ | |
| address_book | search_contact | ✅ | |
| address_book | add_contact | ✅ | 전화/회사 등 모든 필드 채우기 |
| address_book | add_organization | ✅ | 신규 |
| address_book | comment_contact | ✅ | |
| tasks | view_tasks | ✅ | |
| tasks | create_or_update_task | ✅ | 시작일=오늘, 마감일=랜덤, 저장 버튼 |
| tasks | complete_task | ✅ | |
| tasks | comment_task | ✅ | |
| tasks | manage_category | ✅ | |
| tasks | assign_category | ✅ | 신규, 빈 드롭다운 안내 포함 |
| notes | view_notes | ✅ | |
| notes | create_note | ✅ | {notebook} = 계정 기반 노트북 선택 |
| notes | create_or_edit_note | ✅ | |
| notes | comment_note | ✅ | |
| notes | manage_notebook | ✅ | |
| bookmarks | view_bookmarks | ✅ | |
| bookmarks | create_bookmark | ✅ | |
| bookmarks | manage_bookmark | ✅ | |

**총 23개 액션**

---

## DMS 액션 목록 (현재)

| 모듈 | 액션 | 테스트 포함 | 비고 |
|------|------|------------|------|
| files | view_files | ✅ | |
| files | view_recent | ✅ | |
| files | view_favorites | ✅ | |
| files | browse_directory | ✅ | |
| files | upload_file | ✅ | {folder_nav} 위치 지정, 템플릿 선택(여백/Meeting notes/Product plan/Readme) |
| files | create_folder | ✅ | {folder_nav} 위치 지정 |
| files | rename_file | ✅ | 실제 메뉴명 '이름 바꾸기' 사용, 컨텍스트 메뉴 전체 항목 안내 |
| files | move_file | ✅ | 실제 메뉴명 '이동이나 복사' 사용, 컨텍스트 메뉴 전체 항목 안내 |
| files | team_folder_browse | ✅ | 부서/직급 폴더 구조 안내 |
| files | team_folder_create | ✅ | |
| sharing | share_file | ✅ | 공유 옵션 버튼(... 아님), 내부 공유 검색창 → {share_target} 입력 후 클릭 |
| sharing | share_with_link | ✅ | 공유 옵션 버튼 사용 |
| search | search_files | ✅ | 검색 후 결과 클릭까지 수행 |
| common | search | ✅ | 검색 후 결과 클릭까지 수행 |

**총 14개 액션**

### DMS 역할 컨텍스트 (2026-05-04 추가)
- `_parse_employee()`, `_DEPT_CONTEXT`, `_ROLE_CONTEXT` 추가
- `system_prompt(cfg)` → EMPLOYEE_ID 기반 부서/역할 컨텍스트 주입
- `_get_folder_nav(cfg)` → 개인 파일 / Team folders/{dept} / Team folders/{role} 중 랜덤
- `_get_share_targets(cfg)` → 직원 표시 이름 + 부서명 + 직급명 혼합 목록
---

## 삭제된 액션 이력

| 액션 | 삭제 이유 | 날짜 |
|------|---------|------|
| summary.view_summary | 단순 탭 클릭, 의미 없는 행동 | 2026-05-04 |
| groupoffice.email.read_inbox | 없는 모듈 | 2026-04-30 |
| bookmarks.manage_category | 불필요 | 2026-05-04 |

---

## 알려진 이슈 / 기술 주의사항

- **캘린더 카테고리 드롭다운**: 카테고리 미생성 시 드롭다운이 비어 있음. `manage_category`로 먼저 생성 필요. `assign_category` 템플릿에 안내 문구 포함.
- **태스크 카테고리 드롭다운**: 동일 문제. `tasks.manage_category`로 먼저 생성 필요.
- **DMS navigate_to**: `browser_session.navigate_to()`는 3초 SPA 타임아웃 → `runner.py`에서 Playwright `goto()`로 직접 이동.
- **GroupOffice ExtJS**: 일부 요소가 `offsetParent=null`로 browser-use에 보이지 않을 수 있음.
- **use_vision=False**: screenshot 15초 타임아웃 방지용, Agent에 반드시 설정.
- **노트북 선택**: `_get_notebooks(cfg)` → `[dept, "{dept} {role}"]` (예: `["dev", "dev manager"]`)

---

## 향후 검토 항목 (미결)

- [ ] 테스트 실행 결과 기반 템플릿 튜닝
- [ ] DMS 댓글/공유 추가 액션 가능성 검토
- [ ] 캘린더 `assign_category` 실제 동작 확인 (드롭다운 구조)
- [ ] 노트북 선택 실제 동작 확인 (GroupOffice 노트 UI)

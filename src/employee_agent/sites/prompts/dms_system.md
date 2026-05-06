You are operating Nextcloud 33.0.2 at https://dms.kmuinfosec.click.

## Shadow DOM
DMS uses standard HTML DOM — no Shadow DOM boundaries. All elements are directly accessible by their accessible name or selector. Context menus (동작 ···) may render as Vue portal overlays appended to `<body>`; if a menu item is not visible in the current subtree, search the full document body.

## UI Structure
Standard HTML DOM — direct and predictable. Use accessible names (Korean button labels).

## Key UI Elements
- Left navigation: 모든 파일 | 개인 파일 | 최근 | 즐겨찾기 | 공유 | Team folders | 태그 | 삭제된 파일
- Top toolbar: 새로 만들기 (dropdown: 파일 업로드 / 폴더 업로드 / 새 폴더 / 새 텍스트 파일)
- File row actions: 공유 옵션 button, 동작 (···) context menu
- Header: 통합검색 | 알림 | 설정 메뉴 (avatar dropdown → 로그아웃)

## Authentication
Login uses Keycloak SSO: /login → "Login with keycloak" → fill #username/#password → click #kc-login

## Route Diversity
Vary your approach:
- File browsing: left nav click vs breadcrumb vs search
- Sharing: row context menu vs file detail panel

Stop immediately when the goal is achieved. Do not navigate to settings or logout
unless the task explicitly requires it.

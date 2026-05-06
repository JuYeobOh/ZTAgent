# employee-agent

## 개요

ZeroTrust 환경에서 실제 직원 행동을 모사하는 트래픽 생성 에이전트입니다.
Controller의 지시에 따라 GroupOffice, DMS 등 내부 시스템에 브라우저 기반 업무를 자동으로 수행합니다.

## 환경변수 목록

| 변수명 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `EMPLOYEE_ID` | 필수 | - | 에이전트 식별자 (예: `emp-001`) |
| `LOCATION_ID` | 필수 | - | 물리적/논리적 위치 ID |
| `WORKER_GROUP` | 필수 | - | 에이전트가 속한 워커 그룹 |
| `CONTROLLER_URL` | 필수 | - | Controller 서버 URL |
| `PROFILE_DIR` | 선택 | `/app/profile` | 브라우저 프로파일 저장 경로 |
| `RESULTS_DIR` | 선택 | `/app/results` | 작업 결과 저장 경로 |
| `LOG_DIR` | 선택 | `/app/logs` | 로그 저장 경로 |
| `TZ` | 선택 | `Asia/Seoul` | 타임존 |
| `BROWSER_HEADLESS` | 선택 | `true` | 헤드리스 브라우저 모드 |
| `LLM_BASE_URL` | 필수 | - | LLM API 엔드포인트 URL |
| `LLM_MODEL` | 필수 | - | 사용할 LLM 모델명 |
| `LLM_API_KEY` | 필수 | - | LLM API 키 |
| `LLM_DAILY_BUDGET_USD` | 선택 | `5.0` | LLM 일일 사용 한도 (USD) |
| `PER_TASK_LLM_TIMEOUT_S` | 선택 | `120` | 태스크당 LLM 타임아웃 (초) |

## LLM 설정 예시

### OpenAI
```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
```

### Anthropic (OpenAI 호환)
```bash
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_API_KEY=sk-ant-...
```

### Ollama (로컬)
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2
LLM_API_KEY=ollama
```

## 실행 방법

```bash
# 이미지 빌드
docker build -t employee-agent:latest .

# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

환경변수는 `.env` 파일에 정의하거나 셸 환경에서 직접 export 후 실행합니다.

```bash
# .env 파일 예시
EMPLOYEE_ID=emp-001
LOCATION_ID=loc-seoul-01
WORKER_GROUP=general
CONTROLLER_URL=http://controller:8000
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
```

## 아키텍처

```
Controller
    |
    | (HTTP / WebSocket — outbound only)
    v
employee-agent (Docker container)
    |
    | (Playwright 브라우저 자동화)
    v
GroupOffice / DMS / 기타 내부 시스템
```

- **Controller**: 태스크 스케줄링 및 에이전트 관리 서버
- **employee-agent**: Controller로부터 태스크를 수신하고 브라우저를 통해 내부 시스템과 상호작용
- **GroupOffice / DMS**: 에이전트가 실제 업무를 수행하는 대상 내부 애플리케이션

컨테이너는 인바운드 포트를 노출하지 않으며, 모든 통신은 아웃바운드로만 이루어집니다.

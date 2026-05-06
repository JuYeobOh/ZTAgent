FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# 소스 복사
COPY src/ src/
COPY tools/ tools/

# EXPOSE 없음 — outbound only

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul
ENV BROWSER_HEADLESS=true
ENV ANONYMIZED_TELEMETRY=false

ENTRYPOINT ["python", "-m", "employee_agent"]

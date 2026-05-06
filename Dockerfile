FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# 소스를 먼저 복사 (editable install은 src/가 존재해야 동작)
COPY pyproject.toml .
COPY src/ src/
COPY tools/ tools/
RUN pip install --no-cache-dir -e .

# EXPOSE 없음 — outbound only

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul
ENV BROWSER_HEADLESS=true
ENV ANONYMIZED_TELEMETRY=false

ENTRYPOINT ["python", "-m", "employee_agent"]

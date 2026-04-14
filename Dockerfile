FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装构建/运行依赖（psycopg[binary] 不需要额外 libpq-dev）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

# 默认安装 API 依赖；如需 PostgreSQL 可构建时传入 --build-arg PIP_EXTRAS="api,postgres"
ARG PIP_EXTRAS=api
RUN pip install --upgrade pip \
    && pip install ".[${PIP_EXTRAS}]"

RUN useradd --create-home --shell /bin/bash appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV DPM_AGENT_API_HOST=0.0.0.0 \
    DPM_AGENT_API_PORT=8000

EXPOSE 8000
VOLUME ["/app/data"]

CMD ["dpm-agent-api", "--host", "0.0.0.0", "--port", "8000"]

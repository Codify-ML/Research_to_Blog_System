FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --frozen --no-dev

COPY apps /app/apps
COPY packages /app/packages
COPY scripts /app/scripts

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "apps/ui/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--browser.gatherUsageStats", "false", "--server.headless", "true"]

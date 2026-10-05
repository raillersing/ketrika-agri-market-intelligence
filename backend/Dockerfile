FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# Install system dependencies (WeasyPrint / Pango, PostgreSQL client libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libjpeg-dev \
    libopenjp2-7 \
    libffi-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency management
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /bin/

# Create non-root app user
RUN useradd -m -u 1000 app

WORKDIR /app

# Install project dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN uv pip install --system -e ".[dev,geo,ml]"

# Copy tests and other files
COPY tests/ ./tests/

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "ketrika.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

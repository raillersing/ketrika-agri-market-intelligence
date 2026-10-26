FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

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
COPY --from=ghcr.io/astral-sh/uv:0.12.24@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a /uv /uvx /bin/

# Create non-root app user
RUN useradd -m -u 1000 app

WORKDIR /app
RUN chown app:app /app
USER app

# Install project dependencies
COPY --chown=app:app pyproject.toml uv.lock README.md ./
COPY --chown=app:app src/ ./src/
RUN uv sync --locked --compile-bytecode --extra dev --extra geo --extra ml

# Copy tests and other files
COPY --chown=app:app tests/ ./tests/

EXPOSE 8000

CMD ["uvicorn", "ketrika.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Browser tooling is opt-in and never added to the application runtime stage.
FROM base AS backend-browser
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ketrika-browsers
RUN uv sync --locked --compile-bytecode --extra dev --extra geo --extra ml --extra browser
USER root
RUN python -m playwright install-deps chromium \
    && mkdir /opt/ketrika-browsers && chown app:app /opt/ketrika-browsers
USER app
RUN python -m playwright install chromium

# Default builds remain the application stage, without browser dependencies.
FROM base AS runtime

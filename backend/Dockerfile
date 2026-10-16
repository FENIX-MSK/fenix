# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12-python3.14-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.14-slim-bookworm
RUN useradd --create-home --uid 10001 fenix
WORKDIR /app
COPY --from=build --chown=fenix:fenix /app/.venv /app/.venv
COPY --chown=fenix:fenix src ./src
COPY --chown=fenix:fenix alembic.ini ./
COPY --chown=fenix:fenix migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER fenix
EXPOSE 8000
CMD ["uvicorn", "fenix.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

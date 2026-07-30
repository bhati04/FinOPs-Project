# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 cloudwise \
    && useradd --uid 10001 --gid cloudwise --no-create-home --shell /usr/sbin/nologin cloudwise

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER cloudwise
EXPOSE 8000

FROM base AS production
CMD ["uvicorn", "cloudwise.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS development
USER root
COPY tests ./tests
RUN python -m pip install --editable ".[dev]"
USER cloudwise
CMD ["uvicorn", "cloudwise.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]

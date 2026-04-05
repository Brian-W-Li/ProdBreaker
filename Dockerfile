# Stage 1: build dependencies
FROM python:3.13 AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: runtime
FROM python:3.13

WORKDIR /app

COPY --from=builder /app/.venv .venv

COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["gunicorn", "run:app", "--workers=4", "--threads=25", "--worker-class=gthread", "--bind=0.0.0.0:8000", "--timeout=60", "--backlog=512", "--keep-alive=5"]

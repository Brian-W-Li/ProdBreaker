# ProdBreaker — URL Shortener API

A production-grade URL shortener built on Flask · Peewee · PostgreSQL · Redis · Nginx · Gunicorn, with full observability (Prometheus + Grafana), load testing (k6), and chaos engineering.

**Stack:** Flask · Peewee ORM · PostgreSQL 16 · Redis 7 · Gunicorn · Nginx · Prometheus · Grafana · Docker Compose · Docker Swarm · uv

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd ProdBreaker

# 2. Configure
cp .env.example .env   # add DISCORD_WEBHOOK_URL if you want alerts

# 3. Start everything
docker compose up --build -d

# 4. Seed the database (users → urls → events, order matters for FK constraints)
docker compose cp users.csv web:/app/users.csv
docker compose cp urls.csv  web:/app/urls.csv
docker compose cp events.csv web:/app/events.csv
docker compose exec web python load_csv.py users.csv urls.csv events.csv
# → Loaded 400 rows into User ...
# → Loaded 2000 rows into Url ...
# → Loaded 3422 rows into Event ...

# 5. Verify
curl http://localhost:${APP_PORT:-8000}/health
# → {"status": "ok"}
```

| Service | Default URL | Env var to change port |
|---|---|---|
| API | http://localhost:8000 | `APP_PORT` |
| Grafana | http://localhost:3000 | `GRAFANA_PORT` |
| Prometheus | http://localhost:9090 | `PROMETHEUS_PORT` |
| Alertmanager | http://localhost:9093 | `ALERTMANAGER_PORT` |

**Key endpoints to verify the stack is working:**

| Endpoint | What it checks |
|---|---|
| `GET /health` | App is up |
| `GET /metrics` | Prometheus metrics being collected |
| `GET /logs` | Structured JSON logs (add `?lines=N` for more) |
| `GET /products` | DB + Redis cache (`X-Cache: HIT/MISS` header) |

---

## API Reference

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — always 200 if app is running |

### Users

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/users` | Create a user `{username, email}` |
| `GET` | `/users` | List all users (supports `?page=&per_page=`) |
| `GET` | `/users/<id>` | Get user by ID |
| `PUT` | `/users/<id>` | Update username and/or email |
| `POST` | `/users/bulk` | Bulk import from CSV (`multipart/form-data`, field `file`) |

### URLs

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/urls` | Create a short URL `{user_id, original_url, title?}` |
| `GET` | `/urls` | List all URLs (supports `?user_id=`) |
| `GET` | `/urls/<id>` | Get URL by ID |
| `PUT` | `/urls/<id>` | Update `title` and/or `is_active` |
| `GET` | `/<short_code>` | Redirect to original URL (302); 410 if deactivated |

### Events / Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/events` | List all events (`created`, `updated`, `clicked`) |

### Logs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/logs` | Returns last 100 log entries as a JSON array. Use `?lines=N` to override (max 1000). |

Log entries look like:
```json
[
  {"timestamp": "2026-04-04 22:43:09,858", "level": "INFO", "logger": "app", "message": "request started", "method": "GET", "path": "/health"},
  {"timestamp": "2026-04-04 22:43:09,862", "level": "INFO", "logger": "app", "message": "request finished", "method": "GET", "path": "/health", "status": 200, "duration_ms": 4.07}
]
```

Logs are written to a Docker volume (`app_logs`) so they persist across container restarts.

### Response formats

All errors return JSON:
```json
{"error": "Not Found", "message": "User 99 not found"}
```

All datetimes are ISO 8601 strings: `"2025-09-19T22:25:05"`

Cache header on `/products`: `X-Cache: HIT` or `X-Cache: MISS`

---

## Local Development (without Docker)

**Prerequisites:** Python 3.13+, PostgreSQL, Redis, [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync                        # install dependencies
cp .env.example .env           # set DATABASE_HOST=localhost for local Postgres
uv run run.py                  # starts on APP_PORT (default 8000)
```

---

## Running Tests

```bash
uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

**53 tests, 86% coverage.** Tests use in-memory SQLite — no Postgres or Redis required.

```
tests/test_health.py     — health endpoint
tests/test_errors.py     — 404/405 return JSON not HTML
tests/test_products.py   — products route + Redis cache + chaos
tests/test_users.py      — full user CRUD + bulk CSV
tests/test_urls.py       — full URL CRUD + short code + redirect + events
tests/test_events.py     — event listing and detail parsing
```

---

## Load Testing

```bash
k6 run load_test.js
```

Ramps to 500 concurrent users over 90 seconds. Each run uses a unique timestamp prefix for generated usernames (via k6's `setup()` function), so re-running against a populated database does not produce 409 conflicts — **do not remove the `setup()` function** from `load_test.js`.

**Results (10-core MacBook, 3 web replicas):**

| Metric | Result | Target |
|---|---|---|
| Error rate | 0.00% | < 5% |
| p95 latency | ~470ms | < 500ms |
| Throughput | ~700 req/s | 100+ req/s |

Outputs `load-summary.html` (HTML report) and `load-summary.json`.

---

## Seeding the Database

Three CSV files are included as seed data. They must be loaded **in this order** (FK constraint: urls reference users, events reference both):

```bash
docker compose exec web python load_csv.py users.csv urls.csv events.csv
```

`load_csv.py` auto-detects the model from the CSV headers, preserves explicit IDs, and resets PostgreSQL sequences after each bulk insert. Multiple files can be passed in one invocation.

> **Important:** `DATABASE_HOST=db` in `.env` is the Docker-internal service name. Running `load_csv.py` directly from the host will fail with a DNS error — always run it via `docker compose exec web`.

The `product` table requires no seed data. `/products` returns `[]` by design until product rows are inserted.

---

## Observability

Grafana dashboard auto-loads at http://localhost:3000 with 10 panels:

- **Latency** — p50/p95/p99 time series + p95 gauge (red at >500ms)
- **Traffic** — req/s by status code + total RPS
- **Errors** — 5xx rate (red at >5%)
- **Saturation** — Postgres connections vs max, Redis memory
- **Cache** — Redis hit rate
- **Uptime** — App status (UP/DOWN)

**Alerts** fire to Discord on:
- p95 latency > 500ms
- 5xx error rate > 5%
- Zero traffic for 2 minutes
- Postgres connections > 80% of max
- Redis memory > 80%
- Flask app unreachable

Set your webhook URL directly in [monitoring/alertmanager/alertmanager.yml](monitoring/alertmanager/alertmanager.yml) — replace the `url:` value under the `discord` receiver, then `docker compose restart alertmanager`.

---

## Project Structure

```
ProdBreaker/
├── app/
│   ├── __init__.py              # App factory, error handlers, metrics
│   ├── cache.py                 # Redis helpers (cache_get, cache_set)
│   ├── database.py              # PooledPostgresqlDatabase, BaseModel
│   ├── models/
│   │   ├── product.py           # Product model
│   │   ├── user.py              # User model
│   │   ├── url.py               # Url model (short codes)
│   │   └── event.py             # Event model (analytics)
│   ├── logging_config.py        # JSON structured logging (stdout + file)
│   └── routes/
│       ├── products.py          # GET /products
│       ├── users.py             # /users CRUD + bulk
│       ├── urls.py              # /urls CRUD
│       ├── events.py            # GET /events
│       └── logs.py              # GET /logs (view logs without SSH)
├── monitoring/
│   ├── prometheus/              # prometheus.yml + alerts.yml
│   ├── alertmanager/            # alertmanager.yml (Discord routing)
│   └── grafana/                 # Dashboard JSON + provisioning
├── nginx/
│   └── nginx.conf               # Reverse proxy + stub_status
├── tests/                       # pytest suite (49 tests)
├── Dockerfile                   # Multi-stage: builder + runtime (python:3.13)
├── docker-compose.yml           # Local dev: app + db + redis + nginx + monitoring
├── docker-stack.yml             # Docker Swarm: 3 web replicas, self-healing chaos demo
├── load_test.js                 # k6 load test (500 VUs)
├── load_csv.py                  # CSV seed data loader
├── RUNBOOK.md                   # 3 AM emergency guide
├── DECISION_LOG.md              # Why we chose each technology
├── CAPACITY_PLAN.md             # How many users, what breaks first
├── FAILURE_MODES.md             # What breaks + chaos reproduction
└── PERFORMANCE_REPORT.md        # Load test results + bottleneck analysis
```

---

## Documentation

| Document | Contents |
|---|---|
| [RUNBOOK.md](RUNBOOK.md) | Step-by-step alert response guides |
| [DECISION_LOG.md](DECISION_LOG.md) | Why Gunicorn, Redis, Nginx, Postgres pool, etc. |
| [CAPACITY_PLAN.md](CAPACITY_PLAN.md) | Load limits, scaling strategies, weakest links |
| [FAILURE_MODES.md](FAILURE_MODES.md) | What breaks, observed responses, recovery steps |
| [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) | Benchmarks, bottleneck fixes, before/after numbers |

---

## Troubleshooting

**`/products` returns 503 "Database is unavailable"**
The `product` table does not exist. This happens if the container image was built before `Product` was added to `db.create_tables()` in `app/__init__.py`. Rebuild: `docker compose up --build -d`.

**`load_csv.py` fails with "could not translate host name db"**
You are running the script from the host. `DATABASE_HOST=db` only resolves inside Docker. Use `docker compose exec web python load_csv.py ...` instead.

**k6 `create user 201` failing at high rate (409 Conflict)**
The database has users from a previous run and the `setup()` function was removed from `load_test.js`. Restore `setup()` — it generates a per-run `runId` that prefixes all generated usernames, preventing collisions across runs. Do not truncate the database to work around this.

**pytest fails with `could not translate host name db`**
`init_db()` is overwriting the test's SQLite database with a Postgres connection. Ensure `app/database.py` only calls `db.initialize()` (and registers request hooks) inside `if db.obj is None:`. The conftest sets `db` to SQLite before calling `create_app()`, so the guard prevents the overwrite.

**pytest fails with `no such table: user`**
The SQLite in-memory connection was closed between requests. Flask's `teardown_appcontext` hook calls `db.close()`, which destroys `:memory:`. The fix: request lifecycle hooks must be inside the `if db.obj is None:` guard so they are not registered in test mode. The conftest calls `db.connect()` once at session scope to keep the connection alive.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `8000` | Host port for the API |
| `GRAFANA_PORT` | `3000` | Host port for Grafana |
| `PROMETHEUS_PORT` | `9090` | Host port for Prometheus |
| `ALERTMANAGER_PORT` | `9093` | Host port for Alertmanager |
| `DATABASE_NAME` | `hackathon_db` | Postgres database name |
| `DATABASE_HOST` | `db` | Postgres host (`localhost` for local dev without Docker) |
| `DATABASE_PORT` | `5432` | Host port for Postgres |
| `DATABASE_USER` | `postgres` | Postgres user |
| `DATABASE_PASSWORD` | `postgres` | Postgres password |
| `REDIS_HOST` | `redis` | Redis host (`localhost` for local dev without Docker) |
| `REDIS_PORT` | `6379` | Host port for Redis |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |
| `DISCORD_WEBHOOK_URL` | — | Discord webhook for alerts (set in `.env`, picked up by docker-compose) |
| `FLASK_DEBUG` | `true` | Enable Flask debug mode |
| `LOG_FILE` | `logs/app.log` | Path to the JSON log file (inside container: `/app/logs/app.log`) |

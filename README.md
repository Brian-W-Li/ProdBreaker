# ProdBreaker — URL Shortener API

A production-grade URL shortener built on Flask · Peewee · PostgreSQL · Redis · Nginx · Gunicorn, with full observability (Prometheus + Grafana), load testing (k6), and chaos engineering.

**Stack:** Flask · Peewee ORM · PostgreSQL 16 · Redis 7 · Gunicorn · Nginx · Prometheus · Grafana · Docker Compose · uv

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd ProdBreaker

# 2. Configure
cp .env.example .env   # add DISCORD_WEBHOOK_URL if you want alerts

# 3. Start everything
docker compose up --build -d

# 4. Verify
curl http://localhost:8000/health
# → {"status": "ok"}
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Grafana | http://localhost:3000 (admin / admin) |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |

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

### Events / Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/events` | List all events (`created`, `updated`) |

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
cp .env.example .env           # set DATABASE_HOST=localhost
uv run run.py                  # starts on port 8000
```

---

## Running Tests

```bash
uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

**49 tests, 92% coverage.** Tests use in-memory SQLite — no Postgres required.

```
tests/test_health.py     — health endpoint
tests/test_errors.py     — 404/405 return JSON not HTML
tests/test_products.py   — products route + Redis cache + chaos
tests/test_users.py      — full user CRUD + bulk CSV
tests/test_urls.py       — full URL CRUD + short code + events
tests/test_events.py     — event listing and detail parsing
```

---

## Load Testing

```bash
k6 run load_test.js
```

Ramps to 500 concurrent users over 90 seconds.

**Results (10-core MacBook):**

| Metric | Result | Target |
|---|---|---|
| Error rate | 1.22% | < 5% |
| p95 latency | 251ms | < 500ms |
| Throughput | 2,528 req/s | 100+ req/s |

Outputs `load-summary.html` (HTML report) and `load-summary.json`.

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

Set `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...` in `.env` to enable.

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
│   └── routes/
│       ├── products.py          # GET /products
│       ├── users.py             # /users CRUD + bulk
│       ├── urls.py              # /urls CRUD
│       └── events.py            # GET /events
├── monitoring/
│   ├── prometheus/              # prometheus.yml + alerts.yml
│   ├── alertmanager/            # alertmanager.yml (Discord routing)
│   └── grafana/                 # Dashboard JSON + provisioning
├── nginx/
│   └── nginx.conf               # Reverse proxy + stub_status
├── tests/                       # pytest suite (49 tests)
├── Dockerfile                   # Multi-stage: builder + runtime
├── docker-compose.yml           # Full stack: app + db + redis + nginx + monitoring
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

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_NAME` | `hackathon_db` | Postgres database name |
| `DATABASE_HOST` | `db` | Postgres host (`localhost` for local dev) |
| `DATABASE_PORT` | `5432` | Postgres port |
| `DATABASE_USER` | `postgres` | Postgres user |
| `DATABASE_PASSWORD` | `postgres` | Postgres password |
| `REDIS_HOST` | `localhost` | Redis host (`redis` in Docker) |
| `REDIS_PORT` | `6379` | Redis port |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |
| `DISCORD_WEBHOOK_URL` | — | Discord webhook for alerts |
| `FLASK_DEBUG` | `true` | Enable Flask debug mode |

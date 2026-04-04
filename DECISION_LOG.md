# Decision Log

Every meaningful technical choice made in this project, why it was made, and what was rejected.

---

## 1. Gunicorn over Flask dev server

**Decision:** Replace `app.run()` with Gunicorn (`21 workers × 4 threads, gthread class`).

**Why:** Flask's built-in server is single-threaded by design — it handles one request at a time. Under our load test (500 VUs), p95 latency was 4.22 seconds and error rate was 50%. Gunicorn with the `gthread` worker class gives each worker multiple threads, allowing I/O-bound requests (DB, Redis) to yield while waiting.

**Worker count formula:** `(2 × CPU cores) + 1 = (2 × 10) + 1 = 21`. This is Gunicorn's official recommendation. Threads per worker set to 4 to handle I/O wait within each worker.

**Rejected:**
- `uvicorn` / `gevent` — async workers would require rewriting all route handlers as async. Not worth it for this stack.
- More workers — diminishing returns past `2×CPU+1`; each worker consumes memory and a connection pool slot.

---

## 2. Nginx as reverse proxy

**Decision:** Put Nginx in front of Gunicorn.

**Why:** Gunicorn is not designed to face the internet directly. Nginx handles:
- Accept queuing — can hold thousands of connections while Gunicorn processes them
- HTTP keepalive pooling to upstream (`keepalive 64`) — reuses TCP connections to Gunicorn instead of opening a new socket per request, eliminating connection overhead at high concurrency
- `worker_connections 4096` — handles burst traffic without dropping connections

**Key config that mattered:** `proxy_http_version 1.1` + `Connection: ""` enables HTTP/1.1 keepalive to upstream. Without this, Nginx uses HTTP/1.0 per request and the `keepalive 64` directive has no effect.

**Rejected:** Load balancer only (no Nginx) — wouldn't solve the connection queuing problem at the OS socket level.

---

## 3. Redis for caching

**Decision:** Cache `GET /products` in Redis with a 60-second TTL. Return `X-Cache: HIT/MISS` header.

**Why:** List endpoints hit PostgreSQL on every request. Under 500 VUs with full table scans, this created a query queue. Redis serves the cached result in ~1ms from memory.

**Cached endpoints:**
- `GET /products` — 60s TTL (static reference data, high read volume)
- `GET /users`, `GET /urls`, `GET /events` — 10s TTL per page/filter combination (write-heavy during load tests, shorter TTL keeps data fresher)

**Cache keys include pagination params** (e.g. `users:p1:pp20`) so different pages have independent cache entries.

**Why Redis over in-process cache (e.g. `functools.lru_cache`):** In-process cache is per-worker — with 21 Gunicorn workers, each worker has its own cache, meaning 21× DB queries per TTL cycle. Redis is shared across all workers and processes.

**Failure mode:** If Redis is down, `cache_get` returns `None` and the request falls through to the DB. Cache is best-effort — the app never fails because Redis is unavailable.

**Rejected:** Memcached — Redis was chosen because it's already in the ecosystem (monitoring exporter available, same Docker network) and supports richer data types if needed later.

---

## 4. PooledPostgresqlDatabase over PostgresqlDatabase

**Decision:** Use Peewee's `PooledPostgresqlDatabase` with `max_connections=20`.

**Why:** Under load testing, switching to Gunicorn without connection pooling caused `Cannot assign requested address` — the OS ran out of ephemeral ports because each request opened and immediately closed a TCP connection to Postgres. The pool keeps 20 persistent connections alive and reuses them. `db.close()` returns the connection to the pool rather than closing the TCP socket.

**Pool size of 20:** Chosen to stay well within Postgres `max_connections=200`. With 21 workers, worst case is 21 connections simultaneously held — 20 is the cap, so one worker may briefly wait. In practice, most requests hit Redis and never need a DB connection.

**Postgres `max_connections=200`:** Default is 100, which was exhausted post-load-test (connections weren't released instantly). Set to 200 via `command: postgres -c max_connections=200` in Docker Compose.

---

## 5. Docker Compose over bare processes

**Decision:** Run the entire stack (app, DB, Redis, Nginx, monitoring) in Docker Compose.

**Why:** Reproducibility. Any machine with Docker can run `docker compose up --build` and get an identical environment. No "works on my machine" issues with Postgres versions, Python versions, or port conflicts.

**Multi-stage Dockerfile:** Stage 1 installs dependencies via `uv` into `.venv`. Stage 2 copies only `.venv` and source — no build tools in the runtime image. Keeps the image lean.

**`restart: unless-stopped` on `web`:** Container auto-restarts on crash. Demonstrated in chaos testing: `docker compose kill web` → app recovers in ~2 seconds without manual intervention.

**Rejected:** Kubernetes for local development — overkill. The project already has K8s infrastructure repos (`kubernetes-repo`, `farming-assistant-cloud`) for production deployments. Docker Compose is appropriate for the hackathon environment.

---

## 6. Prometheus + Grafana 

**Decision:** Self-hosted Prometheus + Grafana + Alertmanager.

**Why:** No external account or API key required. Entire observability stack runs locally in Docker Compose alongside the app. Prometheus scrapes metrics every 10 seconds from 5 exporters (Flask, Nginx, Postgres, Redis, itself).

**Exporters chosen:**
- `prometheus-flask-exporter` — instruments every Flask route automatically with request count, duration histograms, and in-progress gauges
- `nginx-prometheus-exporter` — scrapes Nginx `stub_status` for connection/request counts
- `postgres-exporter` — exposes `pg_stat_activity`, connection counts, query stats
- `redis-exporter` — exposes memory usage, hit/miss ratios, connected clients

**Alertmanager with Discord webhook:** Alerts route to Discord on-call channel. Two severity levels: `warning` (repeats every hour) and `critical` (repeats every 15 minutes). Critical alerts inhibit warnings on the same `alertname` to reduce noise.

---

## 7. Peewee ORM

**Decision:** Use Peewee as the ORM (inherited from project template).

**Why it stayed:** Peewee is lightweight, has no session management complexity, and integrates directly with Flask via `before_request`/`teardown_appcontext` hooks. `PooledPostgresqlDatabase` and `DatabaseProxy` gave us everything needed for connection pooling and test isolation.

**Test isolation approach:** For unit tests, `DatabaseProxy` is re-initialized to an in-memory SQLite database per test. Models are rebound via `test_db.bind([...])`. This avoids any real Postgres dependency in CI.

---

## 8. uv over pip/poetry

**Decision:** Use `uv` as the package manager (inherited from template).

**Why it stayed:** `uv` is 10–100× faster than pip for dependency resolution and installation. `uv sync --frozen` in the Dockerfile installs the exact locked versions without network variance. `uv run` ensures scripts use the project's virtual environment without manual activation.

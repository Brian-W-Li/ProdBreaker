# Failure Modes

Documents what breaks, what the app does, and how to recover.

---

## Bottleneck Report

**Before:** Flask's built-in dev server (`app.run()`) is single-threaded — it processes one request at a time. Under load, every request also hit PostgreSQL directly, serializing on both the server and the DB connection pool.

**After:** Three changes eliminated the bottlenecks:
1. **Gunicorn with 4 workers × 25 threads** (`gthread`) replaces the dev server — 100 concurrent request handlers instead of 1.
2. **Nginx** sits in front as a reverse proxy, accepting connections fast and queuing them to Gunicorn, preventing socket exhaustion under burst load.
3. **Redis cache** on `GET /products` (60s TTL), `GET /users`, `GET /urls`, and `GET /events` (2s TTL) means the DB is hit minimally under load.

**Evidence:** `X-Cache: HIT` / `X-Cache: MISS` headers on every `/products` response.

---

## Load Test

Run with [k6](https://k6.io/docs/get-started/installation/) after `docker compose up --build`:

```bash
k6 run load_test.js
# or target a different host:
k6 run -e BASE_URL=http://localhost:${APP_PORT:-8000} load_test.js
```

Ramps to 500 virtual users over 90 seconds. Thresholds: `<5% error rate`, `p95 < 500ms`.

---

## 1. Database Unreachable at Startup

**Cause:** PostgreSQL is down or credentials are wrong when the app starts.

**What happens:** The app starts successfully (Peewee uses a `DatabaseProxy` — no connection is made until the first request). The first request to any DB-backed route triggers the connection attempt and fails.

**Observed response:**
```json
{"error": "Service Unavailable", "message": "Database is unavailable"}
```
HTTP 503.

**`/health` still returns 200** — it never touches the DB.

**Recovery:** Restore the DB. The next request reconnects automatically via `reuse_if_open=True`.

**To reproduce:**
```bash
docker compose stop db
curl http://localhost:${APP_PORT:-8000}/products  # → 503
docker compose start db
curl http://localhost:${APP_PORT:-8000}/products  # → 200
```

---

## 2. Database Goes Away Mid-Run (Chaos)

**Cause:** DB container killed or network partition while the app is running.

**What happens:** Active requests that hit the DB get an `OperationalError`. The `/products` route catches it and returns 503. The `before_request` hook's `connect(reuse_if_open=True)` will fail on the next request.

**Observed response:**
```json
{"error": "Service Unavailable", "message": "Database is unavailable"}
```
HTTP 503. No stack trace exposed to the client.

**Recovery:** Automatic on next request once DB is back.

**To reproduce:**
```bash
docker compose kill db
curl http://localhost:${APP_PORT:-8000}/products  # → 503 JSON
docker compose start db
curl http://localhost:${APP_PORT:-8000}/products  # → 200
```

---

## 3. Web Container Crashes

**Cause:** Unhandled exception, OOM, or manual `docker kill <container-id>`.

**What happens (plain Compose):** Container exits. Docker's `restart: unless-stopped` policy restarts it automatically on crashes (exit code != 0). Brief downtime (~3–5s for Gunicorn to boot) then the app is back.

**What happens (Docker Swarm):** Swarm's reconciliation loop immediately schedules a replacement task. The dead replica is replaced within 2s; nginx's `proxy_next_upstream` retries requests on the remaining healthy replicas during the brief window. Zero visible errors under load.

**To reproduce (Swarm — recommended):**
```bash
# Get a running web container ID
docker ps --filter name=prodbreaker_web --format "{{.ID}}" | head -1

# Kill it — Swarm replaces it automatically, no manual action needed
docker kill <container-id>

# Watch Swarm reconcile
docker service ps prodbreaker_web
```

**To reproduce (plain Compose):**
```bash
docker kill prodbreaker-web-1     # SIGKILL → exit 137 → restart: unless-stopped fires
curl http://localhost:${APP_PORT:-8000}/health  # → 200 once restarted
```

**Important:** Always use `docker kill` (SIGKILL), NOT `docker stop` or `docker compose stop` (SIGTERM). `stop` is treated as intentional — the restart policy will NOT fire. Only crash-like exits (non-zero exit code) trigger auto-restart.

---

## 4. Route Not Found (404)

**Cause:** Client calls a non-existent endpoint.

**What happens:** Flask's default 404 handler is overridden to return JSON instead of HTML.

**Observed response:**
```json
{"error": "Not Found", "message": "..."}
```
HTTP 404.

---

## 5. Wrong HTTP Method (405)

**Cause:** Client sends `POST /health` or similar.

**Observed response:**
```json
{"error": "Method Not Allowed", "message": "..."}
```
HTTP 405.

---

## 6. Unhandled Exception / Bug in Code

**Cause:** An unexpected exception not caught by route handlers.

**What happens:** The global `@app.errorhandler(Exception)` catches it, logs the full traceback server-side, and returns a safe JSON response to the client.

**Observed response:**
```json
{"error": "Internal Server Error", "message": "An unexpected error occurred"}
```
HTTP 500. Stack trace never reaches the client.

---

## 7. Bad Environment / Missing `.env`

**Cause:** App started without `.env` or with missing variables.

**What happens:** `os.environ.get(...)` falls back to defaults (`localhost`, `postgres`, `hackathon_db`). If those defaults don't match the real DB, see Failure Mode 1.

**Recovery:** Ensure `.env` is present and correct before starting.

---

## 8. Corrupt or Malformed Data Ingestion (CSV)

**Cause:** `products.csv` or other seeding files contain non-numeric data in numeric columns (e.g., "Price: 10" instead of "10").

**What happens:** The `load_csv.py` script uses explicit type casting (`int()`, `float()`) wrapped in `try-except` blocks. 

**Observed behavior:**
- **Robustness:** The script does NOT crash or stop execution.
- **Graceful Skipping:** Faulty rows are caught, an error is logged to stderr, and the script continues to process the next valid row.
- **Data Integrity:** Only valid, correctly-typed data is committed to the PostgreSQL database.

**To reproduce:**
1. Manually edit `products.csv` to include a string in the `price` column.
2. Run `uv run load_csv.py products.csv`.
3. Observe the log output showing the skipped row while other products are successfully loaded.
# Failure Modes

Documents what breaks, what the app does, and how to recover.

---

## Bottleneck Report

**Before:** Flask's built-in dev server (`app.run()`) is single-threaded — it processes one request at a time. Under load, every request also hit PostgreSQL directly, serializing on both the server and the DB connection pool.

**After:** Three changes eliminated the bottlenecks:
1. **Gunicorn with 21 workers × 4 threads** replaces the dev server — 84 concurrent request handlers instead of 1.
2. **Nginx** sits in front as a reverse proxy, accepting connections fast and queuing them to Gunicorn, preventing socket exhaustion under burst load.
3. **Redis cache** on `GET /products` (60s TTL), `GET /users`, `GET /urls`, and `GET /events` (10s TTL) means the DB is hit minimally under load.

**Evidence:** `X-Cache: HIT` / `X-Cache: MISS` headers on every `/products` response.

---

## Load Test

Run with [k6](https://k6.io/docs/get-started/installation/) after `docker compose up --build`:

```bash
k6 run load_test.js
# or target a different host:
k6 run -e BASE_URL=http://localhost:8000 load_test.js
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
curl http://localhost:8000/products  # → 503
docker compose start db
curl http://localhost:8000/products  # → 200
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
curl http://localhost:8000/products  # → 503 JSON
docker compose start db
curl http://localhost:8000/products  # → 200
```

---

## 3. Web Container Crashes

**Cause:** Unhandled exception, OOM, or manual `docker compose kill web`.

**What happens:** Container exits. Docker's `restart: unless-stopped` policy restarts it automatically on unintentional exits (OOM, process crash, daemon restart).

**Observed:** Brief downtime (~8s for Gunicorn to boot 21 workers) then the app is back.

**To reproduce:**
```bash
docker compose kill web           # kills container
docker compose up web -d          # manually start (or let Docker restart on daemon restart)
curl http://localhost:8000/health # → 200
```

**Note:** `docker compose kill` and `docker compose stop` are treated as intentional — Docker will NOT auto-restart in those cases. The policy fires on OOM kills, process crashes, and Docker daemon restarts.

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

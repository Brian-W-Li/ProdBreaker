# Failure Modes

Documents what breaks, what the app does, and how to recover.

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

**What happens:** Container exits. Docker restarts it automatically due to `restart: unless-stopped`.

**Observed:** Brief downtime (~1–2s) then the app is back.

**To reproduce:**
```bash
docker compose kill web
# wait ~2 seconds
curl http://localhost:8000/health  # → 200
```

**Note:** `restart: unless-stopped` does NOT restart if you explicitly `docker compose stop` — only on crashes.

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

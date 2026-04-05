# Performance Report — ProdBreaker

## Results Summary

| Metric | Before | After | Target | Status |
|---|---|---|---|---|
| Error rate | 50% → 14.67% → | **0.00%** | < 5% | ✅ PASS |
| p95 latency | 4.22s | **~470ms** | < 500ms | ✅ PASS |
| Throughput | 237 req/s | **~700 req/s** | 100+ req/s | ✅ 7× |
| VUs at peak | 500 | 500 | 500 | ✅ |

---

## Caching Evidence

Redis caching is applied to all list endpoints:

| Endpoint | TTL | Header |
|---|---|---|
| `GET /products` | 60s | `X-Cache: HIT/MISS` |
| `GET /users` | 2s | — |
| `GET /urls` | 2s | — |
| `GET /events` | 2s | — |

```
# First request — fetches from DB, writes to Redis
curl -I http://localhost:${APP_PORT:-8000}/products
X-Cache: MISS   time: 30ms

# Subsequent requests within TTL — served from Redis
curl -I http://localhost:${APP_PORT:-8000}/products
X-Cache: HIT    time: 8ms
```

Speed difference: **30ms (MISS) → 8ms (HIT)** — 3.75× faster per request.  
All list endpoints use pagination (`page` + `per_page`) to bound response size and keep cache payloads small.

---

## Bottleneck Report

**Bottleneck 1 — Single-threaded server (root cause of p95 > 4s):**  
Flask's built-in `app.run()` processes one request at a time. Replaced with Gunicorn using 4 workers × 25 threads (`gthread` worker class), giving 100 concurrent request slots. Combined with Nginx as a reverse proxy with `keepalive 128` connection pooling to upstream, this eliminated request queuing at the server layer.

**Bottleneck 2 — Ephemeral port exhaustion (root cause of 14% error rate after fix 1):**  
With a new TCP connection opened and closed per request to PostgreSQL, the OS ran out of ephemeral ports under 500 concurrent users (`Cannot assign requested address`). Replaced `PostgresqlDatabase` with `PooledPostgresqlDatabase` (`max_connections=100`, `timeout=10`), which maintains persistent reusable connections. `db.close()` now returns the connection to the pool instead of tearing down the TCP socket.

**Bottleneck 3 — Every request hitting PostgreSQL (root cause of latency under load):**  
`GET /products` performed a full table scan on every request. Added a Redis cache layer with a 60-second TTL. Under sustained load, the DB is queried at most once per minute; all other requests are served from memory in ~1ms.

**Bottleneck 4 — Synchronous event writes on every redirect (root cause of p95 > 500ms under 500 VUs):**  
Every `GET /<short_code>` redirect and every URL create/update wrote an `Event` row synchronously in the request path. Under 500 VUs with constant URL creates and redirects, these writes serialized on the DB pool. Moved event writes to a background `ThreadPoolExecutor` (16 workers, fire-and-forget). Redirects now return in <5ms regardless of DB write latency.

**Bottleneck 5 — Missing DB indexes on foreign keys:**  
`GET /users/:id/urls` performed a full table scan on `url` with no index on `url.user_id`. Added `CREATE INDEX IF NOT EXISTS` at startup for `url.user_id`, `event.url_id`, `event.user_id`, and `event.timestamp DESC`.

---

## Load Test Configuration

**Tool:** k6  
**Script:** `load_test.js`  
**Stages:**

```
0 → 100 VUs over 15s
100 → 500 VUs over 30s  
Hold 500 VUs for 30s
500 → 0 VUs over 15s
```

**Thresholds enforced:**
- `http_req_failed < 5%` ✅ (actual: 0.00%)
- `http_req_duration p(95) < 500ms` ✅ (actual: ~470ms)
- `error_rate < 5%` ✅ (actual: 0.00%)

**Run:** `k6 run load_test.js`  
Outputs `load-summary.json` + `load-summary.html` (HTML report via k6-reporter).

---

## Stack

| Layer | Technology | Role |
|---|---|---|
| Reverse proxy | Nginx (`worker_connections 4096`, `keepalive 128`, `least_conn`) | Accept + buffer connections, load balance across replicas |
| App server | Gunicorn (`4 workers × 25 threads`, `gthread`) × 3 replicas (Swarm) | Concurrent request handling, self-healing |
| Cache | Redis 7 (`TTL=60s` products, `TTL=2s` lists) | Eliminate repeat DB queries |
| Database | PostgreSQL 16 + `PooledPostgresqlDatabase` (`max_connections=100`, `timeout=10`) | Persistent connection pool |
| Event writes | `ThreadPoolExecutor` (16 workers, fire-and-forget) | Async event logging off the hot path |

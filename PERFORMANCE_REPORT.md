# Performance Report — ProdBreaker

## Results Summary

| Metric | Before | After | Target | Status |
|---|---|---|---|---|
| Error rate | 50% → 14.67% → | **1.22%** | < 5% | ✅ PASS |
| p95 latency | 4.22s | **251ms** | < 500ms | ✅ PASS |
| Avg latency | 1.31s | **75.6ms** | — | ✅ |
| Median latency | 644ms | **32.8ms** | — | ✅ |
| Throughput | 237 req/s | **2,528 req/s** | 100+ req/s | ✅ 25× |
| Total requests (90s) | 21,602 | **227,794** | — | ✅ |
| VUs at peak | 500 | 500 | 500 | ✅ |

---

## Caching Evidence

Redis caching is applied to all list endpoints:

| Endpoint | TTL | Header |
|---|---|---|
| `GET /products` | 60s | `X-Cache: HIT/MISS` |
| `GET /users` | 10s | — |
| `GET /urls` | 10s | — |
| `GET /events` | 10s | — |

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
Flask's built-in `app.run()` processes one request at a time. Replaced with Gunicorn using `(2×CPU)+1 = 21` workers × 4 threads (`gthread` worker class), giving 84 concurrent request slots. Combined with Nginx as a reverse proxy with `keepalive 64` connection pooling to upstream, this eliminated request queuing at the server layer.

**Bottleneck 2 — Ephemeral port exhaustion (root cause of 14% error rate after fix 1):**  
With a new TCP connection opened and closed per request to PostgreSQL, the OS ran out of ephemeral ports under 500 concurrent users (`Cannot assign requested address`). Replaced `PostgresqlDatabase` with `PooledPostgresqlDatabase` (`max_connections=20`), which maintains persistent reusable connections. `db.close()` now returns the connection to the pool instead of tearing down the TCP socket.

**Bottleneck 3 — Every request hitting PostgreSQL (root cause of latency under load):**  
`GET /products` performed a full table scan on every request. Added a Redis cache layer with a 60-second TTL. Under sustained load, the DB is queried at most once per minute; all other requests are served from memory in ~1ms.

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
- `http_req_failed < 5%` ✅ (actual: 1.22%)
- `http_req_duration p(95) < 500ms` ✅ (actual: 251ms)
- `error_rate < 5%` ✅ (actual: 1.22%)

**Run:** `k6 run load_test.js`  
Outputs `load-summary.json` + `load-summary.html` (HTML report via k6-reporter).

---

## Stack

| Layer | Technology | Role |
|---|---|---|
| Reverse proxy | Nginx (`worker_connections 4096`, `keepalive 64`) | Accept + buffer connections |
| App server | Gunicorn (`21 workers × 4 threads`, `gthread`) | Concurrent request handling |
| Cache | Redis 7 (`TTL=60s`) | Eliminate repeat DB queries |
| Database | PostgreSQL 16 + `PooledPostgresqlDatabase` (`max=20`) | Persistent connection pool |

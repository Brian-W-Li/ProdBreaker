# Capacity Plan

How many users can ProdBreaker handle? Where is the ceiling, and what breaks first?

---

## Measured Baseline (Load Test Results)

All numbers from `k6 run load_test/load_test.js` on a 10-core MacBook with Docker Desktop.

| Metric | Value |
|---|---|
| Peak concurrent users | 500 VUs |
| Sustained throughput | **2,528 req/s** |
| p50 latency | 32ms |
| p95 latency | 251ms |
| p99 latency | ~400ms |
| Error rate | **1.22%** |
| DB queries per minute | ~1 (Redis cache absorbs the rest) |

---

## Where Is the Ceiling?

### Current stack limits

| Component | Current Config | Limit | What breaks |
|---|---|---|---|
| Gunicorn workers | 21 workers × 4 threads | ~84 concurrent requests | Queue builds, latency rises |
| Postgres pool | `max_connections=20` | 20 simultaneous DB queries | Pool exhaustion → 503 on non-cached routes |
| Postgres server | `max_connections=200` | 200 total connections | `FATAL: too many clients` |
| Nginx | `worker_connections 4096` | 4096 simultaneous connections | Connection drops |
| Redis | Memory-bound | ~1GB default | Cache eviction → more DB hits |
| Docker host | 10 CPUs, ~8GB RAM (Docker) | CPU/RAM saturation | All latency increases |

### Estimated hard ceiling (current config)

**~800–1,000 concurrent users** before p95 latency exceeds 500ms, based on:
- At 500 VUs: p95 = 251ms, headroom remains
- Gunicorn's 84 slots become the bottleneck around 800 concurrent VUs
- Postgres pool of 20 becomes a bottleneck only for cache-miss requests

---

## How to Scale

### Vertical (immediate, no code change)

| Action | Expected gain |
|---|---|
| Increase Gunicorn workers: `--workers=33` (for 16-core host) | +50% throughput |
| Increase `max_connections` pool to 50 | Handles more DB-hitting routes |
| Increase Redis `maxmemory` | Prevents eviction under high cardinality |

### Horizontal (Docker Compose scale)

```bash
docker compose up --scale web=3 -d
```

Nginx round-robins across 3 web instances. Each instance has its own Gunicorn pool. Redis and Postgres are shared. This triples available worker slots to ~252 concurrent request handlers.

**Estimated ceiling with 3 replicas:** ~2,000–2,500 concurrent users.

**Limit at 3 replicas:** Postgres pool — 3 instances × 20 connections = 60 simultaneous DB connections. Increase `max_connections` pool per instance to match.


---

## The Weakest Link Under Load

In order of what breaks first:

1. **Postgres connection pool** — non-cached routes (`/users`, `/urls`, `/events`) each require a DB connection. Pool of 20 means the 21st simultaneous non-cached request waits. Mitigation: cache more routes or increase pool size.

2. **Gunicorn worker slots** — 84 concurrent request slots. Past ~800 VUs, the queue grows faster than it drains. Mitigation: more workers or more replicas.

3. **Redis memory** — not a concern until the cached dataset exceeds available RAM. Products list is small. Mitigation: set `maxmemory` and `maxmemory-policy allkeys-lru`.

4. **Postgres itself** — with `max_connections=200` and a 20-connection pool, Postgres is not the bottleneck. The pool cap protects it.

---

## Cost of Downtime

| Scenario | User impact | Recovery time |
|---|---|---|
| Web container crash | ~2s (Docker restart policy) | Automatic |
| Redis down | Latency increases (DB fallback), no errors | Automatic on restart |
| Postgres down | 503 on all data routes, `/health` still 200 | Manual restart |
| Nginx down | Full outage, no traffic in | `docker compose restart nginx` |

---

## Monitoring Thresholds (Prometheus Alerts)

| Alert | Threshold | Meaning |
|---|---|---|
| `HighLatency` | p95 > 500ms for 1m | Approaching worker saturation |
| `HighErrorRate` | 5xx > 5% for 1m | DB/pool failure |
| `PostgresConnectionSaturation` | >80% of max_connections | Pool nearly exhausted |
| `NoTraffic` | 0 req/s for 2m | App or Nginx down |
| `AppDown` | `up{job="flask"} == 0` | Flask unreachable |

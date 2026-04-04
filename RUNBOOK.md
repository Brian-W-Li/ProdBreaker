# ProdBreaker Runbook — In Case of Emergency

> It is 3 AM. You are not okay. This document is.

---

## Quick Links

| Tool | Default URL | Override via `.env` |
|---|---|---|
| Grafana | http://localhost:3000 (admin / see `.env`) | `GRAFANA_PORT` |
| Prometheus | http://localhost:9090 | `PROMETHEUS_PORT` |
| Alertmanager | http://localhost:9093 | `ALERTMANAGER_PORT` |
| App health | http://localhost:${APP_PORT:-8000}/health | `APP_PORT` |
| App metrics | http://localhost:${APP_PORT:-8000}/metrics | `APP_PORT` |

---

## Alert: `HighErrorRate` — 5xx > 5%

**You will see:** Red error rate panel spiking. Discord message: 🔥 FIRING HighErrorRate.

**Step 1 — Confirm:**
```bash
curl -s http://localhost:${APP_PORT:-8000}/health
curl -s http://localhost:${APP_PORT:-8000}/products
```

**Step 2 — Check logs:**
```bash
docker compose logs web --tail=50
docker compose logs nginx --tail=20
```

**Step 3 — Common causes:**

| Symptom in logs | Cause | Fix |
|---|---|---|
| `relation "product" does not exist` | DB table missing | `docker compose restart web` |
| `too many clients already` | Postgres connection saturation | See **PostgresConnectionSaturation** below |
| `connection refused` | DB or Redis down | `docker compose up db redis` |
| `Cannot assign requested address` | Ephemeral port exhaustion | Restart web: `docker compose restart web` |

**Step 4 — If nothing works:**
```bash
docker compose down && docker compose up -d
```

---

## Alert: `HighLatency` — p95 > 500ms

**You will see:** Latency panel yellow/red. p95 gauge above 500ms.

**Step 1 — Check if it's the cache:**
```bash
curl -I http://localhost:${APP_PORT:-8000}/products | grep X-Cache
```
- `X-Cache: MISS` on every request → Redis is down or cache TTL expired under load.

**Step 2 — Check Redis:**
```bash
docker compose logs redis --tail=20
docker compose exec redis redis-cli ping
```

**Step 3 — Check Postgres query time:**
```bash
docker compose exec db psql -U postgres -c "SELECT pid, query, state, query_start FROM pg_stat_activity WHERE state != 'idle';"
```
Long-running queries → possible table lock or missing index.

**Step 4 — Check worker saturation:**
Grafana → Saturation panel. If Postgres connections near `max_connections` → gunicorn workers are all waiting on DB.
```bash
docker compose restart web
```

---

## Alert: `NoTraffic` — 0 req/s for 2 minutes

**You will see:** Traffic panel flat at zero.

**Step 1:**
```bash
curl http://localhost:${APP_PORT:-8000}/health
```
- Timeout → Nginx is down: `docker compose restart nginx`
- 502 → Web is down: `docker compose restart web`
- 200 → k6/load generator stopped, not an app issue.

**Step 2 — Check all containers:**
```bash
docker compose ps
```
Any container not `Up (healthy)` → `docker compose up <service>`.

---

## Alert: `PostgresConnectionSaturation` — > 80% of max_connections

**You will see:** Saturation panel (Postgres connections) approaching the `max_connections` line.

**Step 1 — See who is connected:**
```bash
docker compose exec db psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

**Step 2 — Kill idle connections:**
```bash
docker compose exec db psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '5 minutes';"
```

**Step 3 — If persistent:** Scale down gunicorn workers in `Dockerfile` or reduce `max_connections` in `app/database.py`.

---

## Alert: `AppDown` — Flask unreachable

**You will see:** `up{job="flask"} == 0` in Prometheus. App uptime stat shows DOWN (red).

```bash
docker compose ps web
docker compose logs web --tail=30
docker compose restart web
```

If web keeps crashing — check for import errors or missing env vars:
```bash
docker compose run --rm web python -c "from app import create_app; create_app()"
```

---

## Sherlock Mode — Finding Root Cause from Dashboard

**Scenario:** Alert fires at 3:14 AM. Error rate 12%. Users see 503s.

1. Open Grafana → **Errors panel** — spike started at 3:12 AM.
2. Check **Traffic panel** — RPS is normal (not zero), so the app is alive.
3. Check **Latency panel** — p95 jumped from 80ms to 3s at same time.
4. Check **Saturation — Postgres Connections** — connections hit 198/200 at 3:12 AM.
5. **Root cause identified:** Connection saturation. DB pool exhausted → requests queue → timeout → 503.
6. Fix: `docker compose exec db psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle';"` → connections drop → error rate returns to 0%.
7. Long-term: Investigate what caused the connection spike (check logs around 3:12 AM).

---

## General Commands

```bash
# Full restart
docker compose down && docker compose up -d

# Restart single service
docker compose restart <web|db|redis|nginx>

# Tail all logs
docker compose logs -f

# Check container health
docker compose ps

# Run load test
k6 run load_test.js

# Check metrics endpoint
curl http://localhost:${APP_PORT:-8000}/metrics | grep flask_http
```

---

## Chaos Reproduction Commands

```bash
# Kill DB — triggers HighErrorRate + 503s on /products
docker compose stop db

# Kill Redis — /products hits DB directly, latency increases
docker compose stop redis

# Kill web — triggers AppDown alert after 30s
docker compose stop web

# Flood connections — triggers PostgresConnectionSaturation
k6 run load_test.js
```

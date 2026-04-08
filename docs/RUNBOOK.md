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
k6 run load_test/load_test.js

# Check metrics endpoint
curl http://localhost:${APP_PORT:-8000}/metrics | grep flask_http
```

---

## Chaos Reproduction Commands

> **Important:** Always use `docker compose kill` or `docker kill` — NOT `docker compose stop`.
> `stop` sends SIGTERM (intentional stop) and `restart: unless-stopped` will NOT restart it.
> `kill` sends SIGKILL (exit 137, treated as a crash) and the restart policy WILL kick in.

```bash
# Kill DB — triggers HighErrorRate + 503s on /products
docker compose kill db

# Kill Redis — /products hits DB directly, latency increases
docker compose kill redis

# Kill web — Docker restarts it automatically via restart: unless-stopped
docker compose kill web

# Flood connections — triggers PostgresConnectionSaturation
k6 run load_test/load_test.js
```

---

## Chaos Engineering — Multi-Instance Resilience

The `web` service runs **3 replicas** (via `--scale web=3`) behind nginx. Killing one replica causes zero visible downtime — nginx retries on a healthy replica and Docker restarts the dead container automatically.

### Setup (Swarm)

```bash
# One-time: clean slate
docker compose down --remove-orphans
docker swarm leave --force 2>/dev/null; true

# Init swarm and build image
docker swarm init
docker build -t prodbreaker-web .

# Deploy the stack
docker stack deploy -c docker-stack.yml prodbreaker

# Wait for all services to come up (~20s)
while true; do clear; docker service ls; sleep 3; done

# Confirm all 3 web replicas are running (look for 3/3)
docker service ls
docker service ps prodbreaker_web
```

### What to watch in Grafana

Open the **bottom row** of the dashboard:

| Panel | What you see during chaos |
|---|---|
| **Instances — Healthy Count** | Drops from 3 → 2 when you kill a replica, recovers to 3 once Docker restarts it |
| **Instances — Per-Instance Up/Down** | The killed instance line drops to 0, then returns to 1 on restart |
| **Instances — Per-Instance RPS** | Traffic redistributes across remaining replicas during the outage |
| **Errors — 5xx Rate** | Should stay at 0% — nginx reroutes requests away from the dead replica |
| **Latency — p95** | May blip slightly during the kill but should not breach 500ms |

### Running the test

**Terminal 1 — keep load running:**
```bash
k6 run load_test/load_test.js
```

**Terminal 2 — kill replicas (Swarm replaces them automatically):**
```bash
# Get running container IDs for web
docker ps --filter name=prodbreaker_web --format "table {{.ID}}\t{{.Names}}"

# Kill one — Swarm detects missing replica and schedules a replacement immediately
docker kill <container-id>

# Kill two at once
docker kill <container-id-1> <container-id-2>

# Watch Swarm replace them
docker service ps prodbreaker_web
```

**Terminal 3 — watch Swarm reconcile (Mac-compatible):**
```bash
while true; do clear; docker service ps prodbreaker_web; echo ""; date; sleep 2; done
```

**What success looks like:**
- Killed task shows `Shutdown` / `Failed`
- New task immediately appears as `Preparing` → `Running`
- Swarm always maintains exactly 3 running replicas
- `docker service logs prodbreaker_web` shows Gunicorn booting on the new task

**What Swarm does:** The reconciliation loop runs continuously. When a task (container) dies, Swarm immediately schedules a replacement — it doesn't wait for a restart, it spins up a brand new task. The desired state (3 replicas) is always enforced. This is true self-healing.

**What nginx does:** `proxy_next_upstream error timeout http_502 http_503 http_504` transparently retries requests on healthy replicas while the replacement starts. The healthcheck `start_period: 10s` ensures the new task is ready before nginx routes to it.

### Scale on the fly

```bash
# Scale to 5 replicas mid-test — Swarm adds 2 more immediately
docker service scale prodbreaker_web=5

# Scale back to 3
docker service scale prodbreaker_web=3
```

### Verify no errors during kill

```bash
# Continuous health check
while true; do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" http://localhost:${APP_PORT:-8000}/health; sleep 0.2; done

# Check error rate via Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(flask_http_request_total{status=~"5.."}[1m]))' | jq '.data.result'
```

### Full reset between tests

```bash
docker stack rm prodbreaker
sleep 10
docker build -t prodbreaker-web .
docker stack deploy -c docker-stack.yml prodbreaker
while true; do clear; docker service ls; sleep 3; done
```

### Troubleshooting

**web stuck at 0/3 — healthcheck failing (no curl in image):**
```bash
# Check what's failing
docker service ps prodbreaker_web --no-trunc
docker ps -a --filter name=prodbreaker_web --format "{{.ID}}" | head -1 | xargs docker logs

# Fix: ensure Dockerfile uses python:3.13 (not slim), rebuild
docker build -t prodbreaker-web .
docker service update --force prodbreaker_web
```

**web keeps restarting in a loop:**
```bash
# Check logs from a recent task
docker ps -a --filter name=prodbreaker_web --format "{{.ID}}" | head -3 | xargs -I{} docker logs {}
```

**nginx stuck at 0/1:**
```bash
docker service ps prodbreaker_nginx --no-trunc
# Usually means web isn't healthy yet — wait for web to show 3/3 first
```

**Leave swarm and go back to plain Compose:**
```bash
docker stack rm prodbreaker
docker swarm leave --force
docker compose up -d --scale web=3
```

### Expected outcomes

| Scenario | Result |
|---|---|
| Kill 1 of 3 replicas | Swarm schedules replacement in <2s, 2 replicas serve traffic meanwhile, no errors |
| Kill 2 of 3 replicas | 1 replica serves all traffic, Swarm brings up 2 replacements, no errors |
| Kill all 3 simultaneously | Brief outage (~10s for healthcheck start_period), all 3 replaced automatically |
| `docker service scale prodbreaker_web=0` | All replicas removed — scale back to restore, demonstrates desired-state enforcement |

```markdown
# Shopify ↔ BC365 Integration (FastAPI + Celery + Redis + Postgres) {#top}

> End-to-end automation for **orders**, **products**, and **inventory** between **Shopify** and **Microsoft Dynamics 365 Business Central (BC365)**.  
> Built with **FastAPI**, **Celery**, **Redis**, **Postgres**, and **Docker**. 🚀

---

- [Highlights](#highlights)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Configure Shopify](#configure-shopify)
- [Configure BC365](#configure-bc365)
- [Run Tests & Debug](#run-tests--debug)
- [Metrics & Observability](#metrics--observability)
- [Environment Variables](#environment-variables)
- [FAQ / Notes](#faq--notes)
- [Roadmap](#roadmap)
- [Changelog](#changelog)
- [Useful Endpoints](#endpoints)

---

## ✨ Highlights {#highlights}

| Capability         | Description |
| ------------------ | ----------- |
| Webhooks           | Handles `orders/create` (easily extendable). |
| BC Sales Orders    | Creates BC **Sales Orders** with **idempotency** via `externalDocumentNumber`[^ext35]. |
| Robustness         | Exponential backoff, retries, structured logs, batch utilities. |
| SKU Mapping        | Map Shopify SKUs → BC Item Numbers with `SKU_MAP_JSON`. |
| Observability      | Prometheus metrics (API + Worker), latency histograms, dedupe counters. |
| Dev & Demo Friendly| Single-process worker mode for **instant metrics** (`-P solo`). |

[^ext35]: BC `externalDocumentNumber` must be ≤ **35 characters**. We enforce trimming and allow custom IDs in the debug endpoint.

---

## 🧭 Architecture {#architecture}

```
Shopify ──► Webhook (orders/create)
│
▼
FastAPI (API)
│
│ \ /metrics (Prometheus)
▼
Redis ◄──────── Celery (worker) ──► BC365 REST
▲ (/salesOrders, /items, ...)
└───────── queue/tasks
```

**Ports**

| Service | URL                         |
| ------- | --------------------------- |
| API     | http://localhost:8000       |
| Worker  | http://localhost:8001 (metrics) |

---

## ✅ Requirements {#requirements}

- Docker & Docker Compose  
- A **Shopify** store (custom app with Admin API)  
- **ngrok** (or similar HTTPS tunnel) for local webhooks  
- **BC365** tenant with **Azure AD App Registration** (Client Credentials) + at least one company (e.g., *CRONUS UK Ltd.*)

---

## ⚙️ Quickstart {#quickstart}

### 1. Clone & configure env
```bash
# bash
cp .env.example .env

# PowerShell
Copy-Item .env.example .env
```

Fill in `.env` (see [Environment Variables](#environment-variables)).

---

### 2. Start services
```bash
docker compose up --build -d
docker compose ps
```

Healthcheck:
```powershell
Invoke-RestMethod "http://localhost:8000/health"
# status: ok
```

---

### 3. Start ngrok & update APP_BASE_URL
```bash
ngrok http http://localhost:8000
```
Copy the `https://` URL into `.env → APP_BASE_URL`, then restart API:
```bash
docker compose up -d --force-recreate api
```

---

### 4. Install the Shopify app (OAuth) {#shopify-install}

Open in browser (replace placeholders):
```
https://<your-ngrok>.ngrok-free.app/oauth/install?shop=<your-shop>.myshopify.com
```

You should see: `Installed for <shop>` ✅

---

## 🛠️ Configure Shopify {#configure-shopify}

**Scopes (example):**
```
read_products,write_products,read_inventory,write_inventory,read_orders
```

**Check/refresh webhooks:**
```powershell
$BASE="https://<your-ngrok>.ngrok-free.app"
$SHOP="<your-shop>.myshopify.com"
$HDR=@{ "ngrok-skip-browser-warning"="true" }

# List webhooks
Invoke-RestMethod -Method GET  "$BASE/debug/webhooks?shop=$SHOP" -Headers $HDR

# Ensure (re-register)
Invoke-RestMethod -Method POST "$BASE/debug/webhooks/ensure?shop=$SHOP" -Headers $HDR
```

---

## 🧩 Configure BC365 {#configure-bc365}

Discover companies:
```powershell
Invoke-RestMethod "http://localhost:8000/debug/bc/companies" | ConvertTo-Json -Depth 6
```

Set company in `.env`:
```ini
BC365_COMPANY_ID=1aa0d663-7688-f011-b9d1-6045bde9b95f
```

Restart:
```bash
docker compose up -d --force-recreate api worker
```

Sanity check items:
```powershell
Invoke-RestMethod "http://localhost:8000/debug/bc/items"
```

---

## 🧪 Run Tests & Debug {#run-tests--debug}

**A) Full path via Shopify**  
- Create a Shopify order whose SKU matches a BC Item Number (e.g., `1896-S`).  
- If not matching, set `SKU_MAP_JSON` in `.env`.

**B) Local synthetic order**  
```powershell
# Unique external number (<= 35 chars)
Invoke-RestMethod -Method POST "http://localhost:8000/debug/orders/test?sku=1896-S&ext=SO101015"
```

Check worker logs:
```bash
docker compose logs -f worker
```

Dedupe test:
```powershell
Invoke-RestMethod -Method POST "http://localhost:8000/debug/orders/test?sku=1896-S&ext=SO101015"
```

---

## 📊 Metrics & Observability {#metrics--observability}

- API metrics: [http://localhost:8000/metrics](http://localhost:8000/metrics)  
- Worker metrics: [http://localhost:8001/metrics](http://localhost:8001/metrics)  

Example queries:
```promql
# Orders pushed per minute
rate(bc_orders_pushed_total[5m])

# Dedupes per minute
rate(bc_orders_deduped_total[5m])

# P50 / P90 / P99 latency
histogram_quantile(0.9, sum by (le) (rate(bc_order_push_seconds_bucket[5m])))
```

---

## 🔧 Environment Variables {#environment-variables}

| Key | Required | Default | Notes |
| --- | -------- | ------- | ----- |
| APP_BASE_URL | ✅ | — | Public base URL for OAuth/webhooks |
| API_HOST / API_PORT | ❌ | 0.0.0.0 / 8000 | API bind |
| DATABASE_URL | ❌ | compose postgres | SQLAlchemy DSN |
| REDIS_URL | ✅ | redis://redis:6379/0 | Celery broker/results |
| SHOPIFY_SHOP | ✅ | — | `<shop>.myshopify.com` |
| SHOPIFY_CLIENT_ID / SECRET | ✅ | — | OAuth App creds |
| SHOPIFY_WEBHOOK_SECRET | ✅ | — | HMAC verification |
| BC365_* | ✅ | — | Azure AD + BC creds |
| SKU_MAP_JSON | ❌ | — | JSON map (Shopify SKU → BC Item) |
| ADMIN_API_TOKEN | ❌ | change-me | Protect debug endpoints |
| PROMETHEUS_ENABLE | ❌ | true | Enable `/metrics` |

---

## ❓ FAQ / Notes {#faq--notes}

- **SKU mismatch?** → Use `SKU_MAP_JSON`  
- **Warnings (`bc_item_not_found`)?** → Check `/debug/bc/items`  
- **400 on externalDocumentNumber?** → Must be ≤ 35 chars  
- **Metrics = 0?** → Scrape worker at `:8001`

---

## ✅ Roadmap {#roadmap}

- [x] Orders: push with idempotency  
- [x] Metrics: pushed, deduped, latency  
- [x] SKU mapping support  
- [ ] Inventory sync (Shopify ⇄ BC)  
- [ ] Product upserts & images  
- [ ] Error dashboard & notifications (Slack/Teams)  

---

## 🗒️ Changelog {#changelog}

**v1.0.0**  
Initial release with OAuth install, webhooks, BC order push, metrics, and debug endpoints.

---

## 🔌 Useful endpoints (dev only) {#endpoints}

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Healthcheck |
| GET | `/metrics` | API metrics |
| POST | `/webhooks/shopify` | Shopify webhook (HMAC verified) |
| GET | `/debug/webhooks?shop=...` | List registered webhooks |
| POST | `/debug/webhooks/ensure?shop=...` | Ensure/re-register webhooks |
| GET | `/debug/bc/companies` | List BC companies |
| GET | `/debug/bc/items` | Sample items |
| POST | `/debug/orders/test?sku=...&ext=...` | Enqueue synthetic order |

---

⬆️ [Back to top](#top)
```

---
```markdown
# Shopify Sync — Monitoring Demo 📊

This folder spins up **Prometheus**, **Alertmanager**, and **Grafana** for a live monitoring demo of the Shopify sync service.  
You’ll get ready-to-use dashboards (inventory updates & latency) and example alerts.

---

## 🚀 1) Bring the stack up

```bash
docker compose -f docker-compose.yml -f monitoring/docker-compose.addon.yml up -d
```

- Grafana → [http://localhost:3000](http://localhost:3000) (default `admin` / `admin`)  
- Prometheus → [http://localhost:9090](http://localhost:9090)  
- Alertmanager → [http://localhost:9093](http://localhost:9093)  
- API → [http://localhost:8000](http://localhost:8000) (already exposes `/metrics`)  

---

## 📈 2) Import the dashboard

In Grafana:

1. **Dashboards → New → Import**  
2. Paste JSON from `monitoring/grafana/shopify-sync-dashboard.json` (or upload file).  
3. Select your **Prometheus datasource** when prompted.  
   - The dashboard uses a variable `${DS_PROMETHEUS}`, so any Prometheus instance will work.  

---

## ⚡ 3) Make the graphs move (seed data)

First, pick a valid `sku` and `location_id` (use debug endpoints):

```powershell
# PowerShell
$loc = (Invoke-RestMethod "http://localhost:8000/debug/inventory/locations").locations[0].id
Invoke-RestMethod "http://localhost:8000/debug/inventory/variant?sku=1896-S"
```

### Generate traffic (PowerShell)
```powershell
# Burst direct updates (increments shopify_inventory_updates_total + latency histogram)
for ($i=0; $i -lt 60; $i++) {
  $qty = Get-Random -Minimum 1 -Maximum 50
  Invoke-RestMethod -Method POST "http://localhost:8000/debug/inventory/set?sku=1896-S&available=$qty&location_id=$loc" | Out-Null
  Start-Sleep -Milliseconds (Get-Random -Minimum 200 -Maximum 900)
}

# Queue a few async updates via Celery (optional)
1..15 | % {
  $qty = Get-Random -Minimum 1 -Maximum 50
  Invoke-RestMethod -Method POST "http://localhost:8000/debug/inventory/queue?sku=1896-S&available=$qty&location_id=$loc" | Out-Null
  Start-Sleep -Milliseconds (Get-Random -Minimum 300 -Maximum 1200)
}
```

### Bash alternative
```bash
loc=$(curl -s http://localhost:8000/debug/inventory/locations | jq -r '.locations[0].id')
for i in {1..60}; do
  qty=$(( 1 + $RANDOM % 50 ))
  curl -s -X POST "http://localhost:8000/debug/inventory/set?sku=1896-S&available=${qty}&location_id=${loc}" >/dev/null
  sleep $(awk -v min=0.2 -v max=0.9 'BEGIN{srand(); print min+rand()*(max-min)}')
done
```

---

## 🚨 4) Alerts (Prometheus)

Create `monitoring/prometheus/alerts.yml`:

```yaml
groups:
- name: shopify-sync
  rules:
  - alert: HighInventoryLatencyP95
    expr: histogram_quantile(0.95, sum(rate(inventory_update_seconds_bucket[5m])) by (le)) > 2
    for: 5m
    labels: { severity: warning }
    annotations:
      summary: "Inventory update latency p95 high"
      description: "p95 latency > 2s for 5m"

  - alert: NoInventoryUpdates
    expr: rate(shopify_inventory_updates_total[10m]) == 0
    for: 10m
    labels: { severity: warning }
    annotations:
      summary: "No inventory updates detected"
      description: "No increments to shopify_inventory_updates_total in the last 10m"

  - alert: InventoryFailureRateHigh
    expr: (sum(rate(inventory_updates_failed_total[5m])) /
           clamp_min(sum(rate(inventory_updates_attempted_total[5m])), 1)) > 0.1
    for: 5m
    labels: { severity: critical }
    annotations:
      summary: "Inventory failure rate > 10%"
      description: "Failures over attempts > 10% (5m window)"
```

Point Prometheus at the file (`prometheus.yml`):
```yaml
rule_files:
  - /etc/prometheus/alerts.yml
```

⚡ The addon already mounts it; otherwise add a volume mapping and reload Prometheus.

**Alertmanager**: edit `monitoring/alertmanager/alertmanager.yml` to configure **email/Slack/webhook** receivers.

---

## 📸 5) Portfolio tips

- Capture a **screenshot** of the Grafana dashboard after running the generator.  
- Record a **30–45s video** clicking through panels and showing an alert firing.  
- Commit these files:
  - `README.md` (this file)
  - `monitoring/grafana/shopify-sync-dashboard.json`
  - `monitoring/prometheus/alerts.yml`

---

## 📊 Grafana Dashboard JSON

Save as: `monitoring/grafana/shopify-sync-dashboard.json`  
> Uses `${DS_PROMETHEUS}` as a **datasource variable** and includes a `source` filter for BC-sync counters.

<details>
<summary>📂 Click to expand dashboard JSON</summary>

```json
{ ... 
---

# Grafana dashboard JSON (save as `monitoring/grafana/shopify-sync-dashboard.json`)

> Uses `${DS_PROMETHEUS}` as a **datasource variable** and includes a `source` filter for BC-sync counters.

```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "type": "stat",
      "title": "Total Inventory Updates (all time)",
      "id": 1,
      "gridPos": { "h": 6, "w": 8, "x": 0, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        { "refId": "A", "expr": "shopify_inventory_updates_total" }
      ],
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "orientation": "auto",
        "textMode": "value",
        "colorMode": "value"
      },
      "fieldConfig": {
        "defaults": { "unit": "none", "thresholds": { "mode": "absolute", "steps": [ { "color": "green" } ] } },
        "overrides": []
      }
    },
    {
      "type": "stat",
      "title": "Updates / min (5m)",
      "id": 2,
      "gridPos": { "h": 6, "w": 8, "x": 8, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        { "refId": "A", "expr": "rate(shopify_inventory_updates_total[5m]) * 60" }
      ],
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "colorMode": "none",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto"
      },
      "fieldConfig": {
        "defaults": { "unit": "opsm" },
        "overrides": []
      }
    },
    {
      "type": "stat",
      "title": "p95 Inventory Update Latency (5m)",
      "id": 3,
      "gridPos": { "h": 6, "w": 8, "x": 16, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        {
          "refId": "A",
          "expr": "histogram_quantile(0.95, sum(rate(inventory_update_seconds_bucket[5m])) by (le))"
        }
      ],
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false }
      },
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "orange", "value": 1 },
              { "color": "red", "value": 2 }
            ]
          }
        },
        "overrides": []
      }
    },
    {
      "type": "timeseries",
      "title": "Inventory Updates per minute",
      "id": 4,
      "gridPos": { "h": 9, "w": 12, "x": 0, "y": 6 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(shopify_inventory_updates_total[$__rate_interval]) * 60",
          "legendFormat": "updates/min"
        }
      ],
      "fieldConfig": { "defaults": { "unit": "opsm" }, "overrides": [] },
      "options": { "legend": { "showLegend": true } }
    },
    {
      "type": "timeseries",
      "title": "Inventory Update Latency (p50/p95/p99)",
      "id": 5,
      "gridPos": { "h": 9, "w": 12, "x": 12, "y": 6 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        {
          "refId": "A",
          "expr": "histogram_quantile(0.50, sum(rate(inventory_update_seconds_bucket[$__rate_interval])) by (le))",
          "legendFormat": "p50"
        },
        {
          "refId": "B",
          "expr": "histogram_quantile(0.95, sum(rate(inventory_update_seconds_bucket[$__rate_interval])) by (le))",
          "legendFormat": "p95"
        },
        {
          "refId": "C",
          "expr": "histogram_quantile(0.99, sum(rate(inventory_update_seconds_bucket[$__rate_interval])) by (le))",
          "legendFormat": "p99"
        }
      ],
      "fieldConfig": { "defaults": { "unit": "s" }, "overrides": [] },
      "options": { "legend": { "showLegend": true } }
    },
    {
      "type": "stat",
      "title": "Failure % (5m) — BC Sync",
      "id": 6,
      "gridPos": { "h": 6, "w": 8, "x": 0, "y": 15 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (sum by (source) (rate(inventory_updates_failed_total[5m])) / clamp_min(sum by (source) (rate(inventory_updates_attempted_total[5m])), 1))",
          "legendFormat": "{{source}}"
        }
      ],
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false }
      },
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "orange", "value": 5 },
              { "color": "red", "value": 10 }
            ]
          }
        },
        "overrides": []
      }
    },
    {
      "type": "timeseries",
      "title": "Attempted vs Succeeded vs Failed (rate, 5m) — BC Sync",
      "id": 7,
      "gridPos": { "h": 9, "w": 16, "x": 8, "y": 15 },
      "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by (source) (rate(inventory_updates_attempted_total[5m]))",
          "legendFormat": "attempted ({{source}})"
        },
        {
          "refId": "B",
          "expr": "sum by (source) (rate(inventory_updates_succeeded_total[5m]))",
          "legendFormat": "succeeded ({{source}})"
        },
        {
          "refId": "C",
          "expr": "sum by (source) (rate(inventory_updates_failed_total[5m]))",
          "legendFormat": "failed ({{source}})"
        }
      ],
      "fieldConfig": { "defaults": { "unit": "ops" }, "overrides": [] },
      "options": { "legend": { "showLegend": true } }
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "style": "dark",
  "tags": ["shopify", "sync", "inventory"],
  "templating": {
    "list": [
      {
        "name": "DS_PROMETHEUS",
        "label": "DS_PROMETHEUS",
        "type": "datasource",
        "query": "prometheus",
        "hide": 0
      },
      {
        "name": "source",
        "label": "source",
        "type": "query",
        "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
        "query": "label_values(inventory_updates_attempted_total, source)",
        "refresh": 2,
        "includeAll": true,
        "multi": true
      }
    ]
  },
  "time": { "from": "now-6h", "to": "now" },
  "timepicker": {},
  "timezone": "",
  "title": "Shopify Sync – Inventory & Orders",
  "uid": "shopify-sync",
  "version": 1,
  "weekStart": ""
}
 ... }
```

</details>

---

⬆️ [Back to top](#shopify-sync--monitoring-demo)
```

---


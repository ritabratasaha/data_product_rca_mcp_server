# Grafana dashboards

## Purpose

Visualize scraped MCP tool metrics. Grafana does not scrape rca-server. Prometheus pulls `/metrics`; Grafana queries that Prometheus datasource and renders the `data-product-rca-server` dashboard.

PromQL catalog: [prometheus.md](prometheus.md).

## Diagram

```mermaid
flowchart LR
  scrape[Prometheus scrape rca-server] --> ds[Grafana datasource prometheus]
  ds --> dash[Dashboard data-product-rca-server]
```

## Setup

`docker compose up` starts Grafana on the `monitoring` network ([`docker-compose.yml`](../docker-compose.yml)):

- Image `grafana/grafana:11.0.0`
- Host port `3001` → container `3000`
- Volumes: `grafana_data`, `./grafana/provisioning` → `/etc/grafana/provisioning`, `./grafana/dashboards` → `/var/lib/grafana/dashboards`
- `depends_on: prometheus`

Login at `http://localhost:3001` with `admin` / `admin`. Override the password with `GF_SECURITY_ADMIN_PASSWORD`. Open the dashboard titled `data-product-rca-server` (uid `rca-server-dashboard`). Refresh interval in the JSON is `5s`; default time range is the last hour.

## Provisioning

**Datasource** ([`grafana/provisioning/datasources/datasources.yml`](../grafana/provisioning/datasources/datasources.yml)):

- Name `Prometheus`, uid `prometheus`, default
- Access `proxy` to `http://prometheus:9090` (Compose service name, Prometheus container port)
- `timeInterval` 5s, `httpMethod` POST
- `editable: false`

**Dashboards** ([`grafana/provisioning/dashboards/dashboards.yml`](../grafana/provisioning/dashboards/dashboards.yml)):

- File provider `RCA Server Dashboards`
- Path `/var/lib/grafana/dashboards` (mounted from `grafana/dashboards/`)
- `updateIntervalSeconds: 30`, `allowUiUpdates: true`

The dashboard JSON is [`grafana/dashboards/rca-server.json`](../grafana/dashboards/rca-server.json). Panels use datasource uid `prometheus`.

## When the dashboard is empty

- Grafana or Prometheus not running (`docker compose up` only `rca-server` skips both)
- rca-server metrics off: `TESTING=true`, missing `mcp-observatory-sdk`, or metrics port bind failure (see [prometheus.md](prometheus.md))
- No tool calls yet (counters stay at zero until MCP tools run)
- Queries filter `job="rca-server"`; a scrape job with another name will not match

## Dashboard panels

Dashboard title: `data-product-rca-server`. Queries live in [prometheus.md](prometheus.md#promql-examples).

| Panel | What it shows |
|---|---|
| Request Rate by Tool | Calls per second by tool |
| Request Latency (p50, p95, p99) | Duration percentiles by tool |
| Active Requests | In-flight tool calls |
| Total Tool Calls | Cumulative invocations |
| Error Rate | Error share of calls over 5m |
| p95 Latency (All Tools) | Combined p95 duration |
| Tool Usage Distribution | Share of calls per tool |
| Request Volume by Tool & Outcome | Success vs error increases over 5m |
| Tool Performance Summary | Calls and average latency by tool |

## Source

- Compose: [`docker-compose.yml`](../docker-compose.yml) (`grafana` service)
- Datasource: [`grafana/provisioning/datasources/datasources.yml`](../grafana/provisioning/datasources/datasources.yml)
- Dashboard provider: [`grafana/provisioning/dashboards/dashboards.yml`](../grafana/provisioning/dashboards/dashboards.yml)
- Dashboard JSON: [`grafana/dashboards/rca-server.json`](../grafana/dashboards/rca-server.json)
- PromQL: [prometheus.md](prometheus.md)

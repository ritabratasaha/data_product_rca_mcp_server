# Prometheus metrics

## Purpose

Scrape-based MCP tool metrics. This server does not remote-write or push to Prometheus. `mcp-observatory-sdk` (`observatory_sdk.instrument`) wraps FastMCP `mcp.tool` registrations, records counters/histograms/gauges in process, and serves them at `/metrics` for Prometheus to pull.

## Diagram

```mermaid
flowchart LR
  call[Agent tool call] --> wrap[Patched mcp.tool wrapper]
  wrap --> mem[In-process Counter Histogram Gauge]
  mem --> http["HTTP /metrics"]
  http --> scrape[Prometheus scrape]
  scrape --> grafana[Grafana dashboard]
```

## Setup

Set `PROMETHEUS_PORT` (default `9090`). Instrumentation runs in [`src/rca_server/tools/registry.py`](../src/rca_server/tools/registry.py) **before** `register_tools()`, so every `mcp.tool(...)` registration is wrapped.

**Docker Compose** (`docker compose up`) starts `rca-server`, Prometheus, and Grafana on the `monitoring` network. Prometheus scrapes `rca-server:9090/metrics` every 5s using job name `rca-server` ([`prometheus/prometheus.yml`](../prometheus/prometheus.yml)). Grafana is auto-provisioned against that Prometheus ([`grafana/dashboards/rca-server.json`](../grafana/dashboards/rca-server.json)).

| Surface | URL |
|---|---|
| Metrics endpoint | `http://localhost:9090/metrics` |
| Prometheus UI | `http://localhost:9091` |
| Grafana | `http://localhost:3001` (admin/admin) |

**Local process** (no Compose): `pip install -e .`, run `rca-server`, then:

```bash
curl http://localhost:9090/metrics
```

Run PromQL in the Prometheus UI or Grafana Explore.

## When metrics are off

- `TESTING=true` (CI and evals)
- `mcp-observatory-sdk` not installed (`observatory_sdk` import fails)
- Metrics port already in use (`OSError` starting the HTTP server)

## Metrics

Defined in `observatory_sdk.metrics` (not in this repo). `service` is always `rca-server` from `instrument(..., service_name="rca-server")`. Prometheus also attaches `job="rca-server"` from the scrape config.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `mcp_tool_calls_total` | Counter | `service`, `tool`, `outcome` | Tool invocations. `outcome` is `success`, `error`, or `timeout` |
| `mcp_tool_duration_seconds` | Histogram | `service`, `tool`, `outcome` | Call duration. Buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10 |
| `mcp_tool_inflight` | Gauge | `service`, `tool` | Calls currently running |

`tool` is the registered MCP tool name (`ping`, `resolve_input`, `generate_column_lineage`, and so on).

## PromQL examples

Copied from [`grafana/dashboards/rca-server.json`](../grafana/dashboards/rca-server.json).

**Request rate by tool**

```promql
sum(rate(mcp_tool_calls_total{job="rca-server"}[1m])) by (tool)
```

**Active requests**

```promql
sum(mcp_tool_inflight{job="rca-server"}) or vector(0)
```

**Total tool calls**

```promql
sum(mcp_tool_calls_total{job="rca-server"}) or vector(0)
```

**Error rate** (errors / all calls over 5 minutes)

```promql
(sum(rate(mcp_tool_calls_total{job="rca-server", outcome="error"}[5m])) or vector(0))
/
(sum(rate(mcp_tool_calls_total{job="rca-server"}[5m])) > 0 or vector(1))
```

**Latency percentiles by tool** (p50 / p95 / p99)

```promql
histogram_quantile(0.50, sum(rate(mcp_tool_duration_seconds_bucket{job="rca-server"}[5m])) by (le, tool))
histogram_quantile(0.95, sum(rate(mcp_tool_duration_seconds_bucket{job="rca-server"}[5m])) by (le, tool))
histogram_quantile(0.99, sum(rate(mcp_tool_duration_seconds_bucket{job="rca-server"}[5m])) by (le, tool))
```

**p95 latency (all tools)**

```promql
histogram_quantile(0.95, sum(rate(mcp_tool_duration_seconds_bucket{job="rca-server"}[5m])) by (le))
```

**Request volume by tool and outcome**

```promql
sum(increase(mcp_tool_calls_total{job="rca-server", outcome="success"}[5m])) by (tool)
sum(increase(mcp_tool_calls_total{job="rca-server", outcome="error"}[5m])) by (tool)
```

**Average latency by tool**

```promql
sum(mcp_tool_duration_seconds_sum{job="rca-server"}) by (tool)
/
sum(mcp_tool_duration_seconds_count{job="rca-server"}) by (tool)
```

**Tool usage distribution** (cumulative counts)

```promql
sum(mcp_tool_calls_total{job="rca-server"}) by (tool)
```

## Dashboard panels

Dashboard title: `data-product-rca-server`.

| Panel | Query |
|---|---|
| Request Rate by Tool | Rate by tool (1m) |
| Request Latency (p50, p95, p99) | Histogram quantiles by tool |
| Active Requests | Inflight gauge |
| Total Tool Calls | Sum of `mcp_tool_calls_total` |
| Error Rate | Error / all rate over 5m |
| p95 Latency (All Tools) | Histogram quantile 0.95 |
| Tool Usage Distribution | Counts by tool |
| Request Volume by Tool & Outcome | `increase` success and error over 5m |
| Tool Performance Summary | Counts by tool plus average latency |

## Source

- Instrumentation: [`src/rca_server/tools/registry.py`](../src/rca_server/tools/registry.py)
- Metric definitions: `mcp-observatory-sdk` (`observatory_sdk.metrics`)
- Scrape config: [`prometheus/prometheus.yml`](../prometheus/prometheus.yml)
- Queries: [`grafana/dashboards/rca-server.json`](../grafana/dashboards/rca-server.json)

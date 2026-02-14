"""
InfraWhisperer — Monitoring MCP Server
========================================
A Model Context Protocol server that wraps Prometheus HTTP API.
Provides PromQL queries, alert listing, and target health checks.
"""

import json
import logging
import os
import random

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("monitoring-mcp-server")

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
DEMO_MODE = False

# Check Prometheus connectivity
try:
    resp = httpx.get(f"{PROMETHEUS_URL}/-/healthy", timeout=3)
    if resp.status_code != 200:
        DEMO_MODE = True
except Exception:
    DEMO_MODE = True

if DEMO_MODE:
    logger.warning("Prometheus not reachable — running in DEMO mode with synthetic metrics")

# ---------------------------------------------------------------------------
# Demo / Synthetic Data
# ---------------------------------------------------------------------------
DEMO_METRICS = {
    "http_request_duration_seconds": {
        "checkout-service": {"p50": 0.045, "p95": 0.320, "p99": 1.200},
        "payment-service": {"p50": 0, "p95": 0, "p99": 0},
        "api-gateway": {"p50": 0.012, "p95": 0.085, "p99": 0.250},
        "user-service": {"p50": 0.030, "p95": 0.150, "p99": 0.400},
    },
    "http_requests_total": {
        "checkout-service": {"2xx": 14532, "4xx": 234, "5xx": 847},
        "payment-service": {"2xx": 0, "4xx": 0, "5xx": 0},
        "api-gateway": {"2xx": 45231, "4xx": 1203, "5xx": 892},
        "user-service": {"2xx": 8923, "4xx": 45, "5xx": 12},
    },
    "container_cpu_usage_seconds_total": {
        "checkout-service": 0.120,
        "payment-service": 0.0,
        "api-gateway": 0.200,
        "user-service": 0.080,
        "inventory-service": 0.060,
    },
    "container_memory_working_set_bytes": {
        "checkout-service": 268435456,
        "payment-service": 0,
        "api-gateway": 478150656,
        "user-service": 188743680,
        "inventory-service": 157286400,
    },
}

DEMO_ALERTS = [
    {
        "alertname": "PaymentServiceDown",
        "severity": "critical",
        "state": "firing",
        "service": "payment-service",
        "summary": "Payment service has been down for > 10 minutes",
        "description": "payment-service pod is in CrashLoopBackOff. Last error: missing vault secret STRIPE_API_KEY",
        "started": "2026-02-14T01:05:00Z",
    },
    {
        "alertname": "HighErrorRate",
        "severity": "warning",
        "state": "firing",
        "service": "checkout-service",
        "summary": "checkout-service 5xx rate > 5% for 5 minutes",
        "description": "Error rate at 5.5% (847 errors / 15613 total). Correlates with payment-service outage.",
        "started": "2026-02-14T01:10:00Z",
    },
    {
        "alertname": "HighMemoryUsage",
        "severity": "warning",
        "state": "firing",
        "service": "api-gateway",
        "summary": "api-gateway memory usage at 89% of limit",
        "description": "Container memory at 456Mi / 512Mi limit. Risk of OOMKill.",
        "started": "2026-02-14T01:15:00Z",
    },
]

DEMO_TARGETS = [
    {"endpoint": "checkout-service:8080/metrics", "state": "up", "lastScrape": "2s ago", "scrapeDuration": "12ms"},
    {"endpoint": "payment-service:8080/metrics", "state": "down", "lastScrape": "5m ago", "scrapeDuration": "0ms", "error": "connection refused"},
    {"endpoint": "api-gateway:8080/metrics", "state": "up", "lastScrape": "1s ago", "scrapeDuration": "8ms"},
    {"endpoint": "user-service:8080/metrics", "state": "up", "lastScrape": "3s ago", "scrapeDuration": "6ms"},
    {"endpoint": "inventory-service:8080/metrics", "state": "up", "lastScrape": "2s ago", "scrapeDuration": "5ms"},
    {"endpoint": "node-exporter:9100/metrics", "state": "up", "lastScrape": "1s ago", "scrapeDuration": "15ms"},
]


def _generate_timeseries(base_value: float, points: int = 30, noise: float = 0.1) -> list:
    """Generate synthetic time series data for demo."""
    import time
    now = int(time.time())
    return [[now - (points - i) * 60, str(base_value + random.uniform(-noise * base_value, noise * base_value))] for i in range(points)]


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "InfraWhisperer Monitoring Server",
    instructions="Prometheus monitoring tools for InfraWhisperer. Query metrics, alerts, and target health.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


@mcp.tool()
async def query_metric(query: str) -> str:
    """Execute a PromQL instant query against Prometheus.

    Args:
        query: A valid PromQL expression (e.g., 'up', 'rate(http_requests_total[5m])').

    Returns:
        Query results as formatted JSON.
    """
    if DEMO_MODE:
        # Parse common queries and return synthetic data
        result = {"status": "success", "query": query}

        if "http_request_duration" in query:
            result["data"] = DEMO_METRICS["http_request_duration_seconds"]
        elif "http_requests_total" in query:
            result["data"] = DEMO_METRICS["http_requests_total"]
        elif "cpu" in query.lower():
            result["data"] = DEMO_METRICS["container_cpu_usage_seconds_total"]
        elif "memory" in query.lower():
            result["data"] = {k: f"{v / 1024 / 1024:.0f}Mi" for k, v in DEMO_METRICS["container_memory_working_set_bytes"].items()}
        elif "up" in query:
            result["data"] = {t["endpoint"].split(":")[0]: 1 if t["state"] == "up" else 0 for t in DEMO_TARGETS}
        else:
            result["data"] = {"info": f"Demo mode: no synthetic data for query '{query}'. Try queries with: http_request_duration, http_requests_total, cpu, memory, up"}

        return json.dumps(result, indent=2)

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
async def query_range(query: str, duration: str = "30m", step: str = "1m") -> str:
    """Execute a PromQL range query against Prometheus to get time series data.

    Args:
        query: A valid PromQL expression.
        duration: How far back to query (e.g., '30m', '1h', '6h', '24h'). Defaults to '30m'.
        step: Resolution step (e.g., '1m', '5m'). Defaults to '1m'.

    Returns:
        Time series data as formatted JSON.
    """
    if DEMO_MODE:
        result = {"status": "success", "query": query, "duration": duration, "step": step}

        if "error" in query.lower() or "5xx" in query.lower():
            result["data"] = {"checkout-service": _generate_timeseries(5.5, noise=0.3), "api-gateway": _generate_timeseries(1.9, noise=0.2)}
        elif "latency" in query.lower() or "duration" in query.lower():
            result["data"] = {"checkout-service_p95": _generate_timeseries(0.320, noise=0.15), "api-gateway_p95": _generate_timeseries(0.085, noise=0.1)}
        elif "cpu" in query.lower():
            result["data"] = {"checkout-service": _generate_timeseries(0.12, noise=0.1), "api-gateway": _generate_timeseries(0.20, noise=0.1)}
        else:
            result["data"] = {"sample_series": _generate_timeseries(random.uniform(0.1, 10))}

        return json.dumps(result, indent=2)

    import time
    end = int(time.time())
    duration_map = {"30m": 1800, "1h": 3600, "6h": 21600, "24h": 86400}
    start = end - duration_map.get(duration, 1800)

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={"query": query, "start": start, "end": end, "step": step})
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
async def get_alerts() -> str:
    """List all currently firing alerts from Prometheus/Alertmanager.

    Returns:
        Formatted list of active alerts with severity, state, summary, and start time.
    """
    if DEMO_MODE:
        lines = [f"🚨 Active Alerts ({len(DEMO_ALERTS)} firing)\n"]
        lines.append(f"{'ALERT':<30} {'SEVERITY':<12} {'SERVICE':<25} {'STARTED':<25}")
        lines.append("-" * 92)
        for a in DEMO_ALERTS:
            lines.append(f"{a['alertname']:<30} {a['severity']:<12} {a['service']:<25} {a['started']:<25}")
            lines.append(f"  Summary: {a['summary']}")
            lines.append(f"  Detail:  {a['description']}")
            lines.append("")
        return "\n".join(lines)

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/alerts")
        data = resp.json()
        if data.get("status") == "success":
            alerts = data["data"]["alerts"]
            if not alerts:
                return "✅ No active alerts."
            return json.dumps(alerts, indent=2)
        return f"Error fetching alerts: {data}"


@mcp.tool()
async def get_targets() -> str:
    """List Prometheus scrape targets and their health status.

    Returns:
        Formatted table of targets with endpoint, state, last scrape time, and duration.
    """
    if DEMO_MODE:
        lines = [f"{'ENDPOINT':<40} {'STATE':<8} {'LAST SCRAPE':<15} {'DURATION':<12} {'ERROR':<30}"]
        lines.append("-" * 105)
        for t in DEMO_TARGETS:
            error = t.get("error", "")
            lines.append(f"{t['endpoint']:<40} {t['state']:<8} {t['lastScrape']:<15} {t['scrapeDuration']:<12} {error:<30}")
        return "\n".join(lines)

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROMETHEUS_URL}/api/v1/targets")
        return json.dumps(resp.json(), indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"Starting Monitoring MCP Server (DEMO_MODE={DEMO_MODE})")
    mcp.run(transport="streamable-http")

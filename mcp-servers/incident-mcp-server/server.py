"""
InfraWhisperer — Incident MCP Server
======================================
A Model Context Protocol server for managing operational runbooks
and incident logging. Provides searchable runbook access and
timestamped incident tracking.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("incident-mcp-server")

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
INCIDENTS_FILE = os.path.join(DATA_DIR, "incidents.json")

# ---------------------------------------------------------------------------
# Runbook Database (embedded for demo — in production these come from the
# Knowledge Graph, but having them here too ensures the incident MCP server
# works standalone)
# ---------------------------------------------------------------------------
RUNBOOKS = [
    {
        "id": "RB-001",
        "title": "Pod CrashLoopBackOff",
        "tags": ["kubernetes", "crashloop", "pod", "restart"],
        "severity": "high",
        "symptoms": [
            "Pod status shows CrashLoopBackOff",
            "Pod restart count is increasing",
            "Container exits with non-zero exit code",
        ],
        "diagnosis": [
            "1. Check pod logs: `kubectl logs <pod> --previous`",
            "2. Describe pod for events: `kubectl describe pod <pod>`",
            "3. Check if the issue is OOMKill (exit code 137) or application error (exit code 1)",
            "4. For exit code 1: check application configuration, secrets, and dependencies",
            "5. For exit code 137: check memory limits vs actual usage",
        ],
        "remediation": [
            "For missing secrets: verify Vault/secrets config and permissions",
            "For OOMKill: increase memory limits in deployment spec",
            "For dependency issues: check downstream service connectivity",
            "Last resort: rollback to previous version",
        ],
    },
    {
        "id": "RB-002",
        "title": "High CPU Usage",
        "tags": ["cpu", "performance", "resource", "throttling"],
        "severity": "medium",
        "symptoms": [
            "CPU usage above 80% for sustained period",
            "Request latency increasing",
            "CPU throttling detected",
        ],
        "diagnosis": [
            "1. Check CPU metrics: `query_metric('rate(container_cpu_usage_seconds_total[5m])')`",
            "2. Identify the hottest pods",
            "3. Check if it's a single pod or all replicas",
            "4. Look for correlated events (deployments, traffic spikes)",
        ],
        "remediation": [
            "Scale the deployment horizontally: `scale_deployment(<name>, <replicas>)`",
            "Check for CPU-intensive operations in application logs",
            "Consider increasing CPU limits if consistently hitting the cap",
        ],
    },
    {
        "id": "RB-003",
        "title": "Database Slow Queries",
        "tags": ["database", "postgres", "slow", "query", "performance"],
        "severity": "medium",
        "symptoms": [
            "Increased p95/p99 latency",
            "Slow query log entries",
            "Connection pool exhaustion",
        ],
        "diagnosis": [
            "1. Check slow queries: use `slow_queries` tool",
            "2. Run EXPLAIN on the offending query",
            "3. Check for missing indexes, sequential scans on large tables",
            "4. Check connection count and pool saturation",
        ],
        "remediation": [
            "Add indexes for commonly filtered/joined columns",
            "Optimize query to reduce sequential scans",
            "Consider read replicas for heavy read workloads",
            "Check and tune connection pool settings",
        ],
    },
    {
        "id": "RB-004",
        "title": "Disk Pressure / Node Storage Full",
        "tags": ["disk", "storage", "node", "pressure", "eviction"],
        "severity": "high",
        "symptoms": [
            "Node condition shows DiskPressure",
            "Pods being evicted",
            "Container image pull failures",
        ],
        "diagnosis": [
            "1. Check node conditions: `list_nodes`",
            "2. Identify large files: container logs, unused images",
            "3. Check PersistentVolume claims",
        ],
        "remediation": [
            "Clean up unused container images: `docker system prune`",
            "Rotate and compress old logs",
            "Expand PersistentVolume if applicable",
            "Add additional nodes to the cluster",
        ],
    },
    {
        "id": "RB-005",
        "title": "Service Returning 5xx Errors",
        "tags": ["5xx", "error", "http", "service", "outage"],
        "severity": "critical",
        "symptoms": [
            "HTTP 500/502/503 error rate spike",
            "Downstream service timeouts",
            "Customer-facing impact",
        ],
        "diagnosis": [
            "1. Check which service(s) are returning errors: `get_alerts`",
            "2. Check service health: `list_pods` + `get_events`",
            "3. Check logs for error details: `get_pod_logs`",
            "4. Check downstream dependencies (database, external APIs)",
            "5. Check recent deployments: was this caused by a code change?",
        ],
        "remediation": [
            "If downstream dependency is down: check and fix that service first",
            "If recent deployment caused it: rollback to previous version",
            "If pod is unhealthy: restart deployment",
            "If overloaded: scale up replicas",
            "Communicate status to stakeholders",
        ],
    },
]

# ---------------------------------------------------------------------------
# Incident Store (file-based for simplicity)
# ---------------------------------------------------------------------------

def _load_incidents() -> list:
    if os.path.exists(INCIDENTS_FILE):
        with open(INCIDENTS_FILE, "r") as f:
            return json.load(f)
    return []


def _save_incidents(incidents: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "InfraWhisperer Incident Server",
    instructions="Operational runbook search and incident logging for InfraWhisperer.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


@mcp.tool()
async def search_runbooks(query: str) -> str:
    """Search operational runbooks by keyword or symptom.

    Args:
        query: Search query — matches against title, tags, symptoms, and content.

    Returns:
        Matching runbooks with diagnosis steps and remediation actions.
    """
    query_lower = query.lower()
    matches = []

    for rb in RUNBOOKS:
        score = 0
        if query_lower in rb["title"].lower():
            score += 10
        for tag in rb["tags"]:
            if query_lower in tag or tag in query_lower:
                score += 5
        for symptom in rb["symptoms"]:
            if query_lower in symptom.lower():
                score += 3
        # Check all text fields
        full_text = json.dumps(rb).lower()
        if query_lower in full_text:
            score += 1

        if score > 0:
            matches.append((score, rb))

    matches.sort(key=lambda x: x[0], reverse=True)

    if not matches:
        return f"No runbooks found matching '{query}'. Available topics: " + ", ".join(rb["title"] for rb in RUNBOOKS)

    results = []
    for _, rb in matches[:3]:
        result = [
            f"📒 {rb['id']}: {rb['title']} (Severity: {rb['severity']})",
            f"   Tags: {', '.join(rb['tags'])}",
            "",
            "   Symptoms:",
            *[f"   • {s}" for s in rb["symptoms"]],
            "",
            "   Diagnosis:",
            *[f"   {step}" for step in rb["diagnosis"]],
            "",
            "   Remediation:",
            *[f"   • {step}" for step in rb["remediation"]],
            "",
            "-" * 60,
        ]
        results.extend(result)

    return f"Found {len(matches)} matching runbook(s):\n\n" + "\n".join(results)


@mcp.tool()
async def log_incident(
    title: str,
    severity: str,
    description: str,
    affected_services: str,
    actions_taken: str = "",
) -> str:
    """Create a timestamped incident log entry.

    Args:
        title: Short incident title (e.g., 'Payment service outage').
        severity: Incident severity — one of: critical, high, medium, low.
        description: Detailed description of the incident and impact.
        affected_services: Comma-separated list of affected services.
        actions_taken: Description of remediation actions taken (if any).

    Returns:
        Confirmation with incident ID and timestamp.
    """
    incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    incident = {
        "id": incident_id,
        "title": title,
        "severity": severity,
        "description": description,
        "affected_services": [s.strip() for s in affected_services.split(",")],
        "actions_taken": actions_taken,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    incidents = _load_incidents()
    incidents.append(incident)
    _save_incidents(incidents)

    logger.info(f"Incident logged: {incident_id} — {title}")

    return (
        f"✅ Incident logged successfully!\n\n"
        f"  ID:        {incident_id}\n"
        f"  Title:     {title}\n"
        f"  Severity:  {severity}\n"
        f"  Services:  {affected_services}\n"
        f"  Timestamp: {incident['created_at']}\n"
        f"  Status:    open"
    )


@mcp.tool()
async def list_incidents(status: str = "all", limit: int = 10) -> str:
    """List recent incidents, optionally filtered by status.

    Args:
        status: Filter by status — 'open', 'resolved', 'all'. Defaults to 'all'.
        limit: Maximum number of incidents to return. Defaults to 10.

    Returns:
        Formatted list of incidents with ID, title, severity, status, and timestamp.
    """
    incidents = _load_incidents()

    if status != "all":
        incidents = [i for i in incidents if i["status"] == status]

    incidents = sorted(incidents, key=lambda x: x["created_at"], reverse=True)[:limit]

    if not incidents:
        return f"No incidents found (filter: status={status})."

    lines = [f"📋 Incidents ({len(incidents)} found, filter: {status})\n"]
    lines.append(f"{'ID':<25} {'SEVERITY':<12} {'STATUS':<10} {'TITLE':<35} {'CREATED':<25}")
    lines.append("-" * 107)
    for inc in incidents:
        lines.append(
            f"{inc['id']:<25} {inc['severity']:<12} {inc['status']:<10} "
            f"{inc['title'][:33]:<35} {inc['created_at'][:19]:<25}"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_incident(incident_id: str) -> str:
    """Get detailed information about a specific incident.

    Args:
        incident_id: The incident ID (e.g., 'INC-20260214-A1B2C3').

    Returns:
        Full incident details including description, affected services, and actions taken.
    """
    incidents = _load_incidents()

    for inc in incidents:
        if inc["id"] == incident_id:
            return json.dumps(inc, indent=2)

    return f"Incident '{incident_id}' not found."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting Incident MCP Server")
    mcp.run(transport="streamable-http")

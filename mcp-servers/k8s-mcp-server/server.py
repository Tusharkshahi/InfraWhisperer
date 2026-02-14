"""
InfraWhisperer — K8s MCP Server
================================
A Model Context Protocol server that wraps kubectl operations.
Provides read-only cluster queries and restricted write operations.

Read tools: list_pods, get_pod_logs, describe_pod, list_deployments, get_events, list_nodes
Write tools: scale_deployment, restart_deployment (assigned only to Remediation Agent in Archestra)
"""

import json
import logging
import os
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("k8s-mcp-server")

# Try to load the Kubernetes client; fall back to demo mode if unavailable
DEMO_MODE = False
try:
    from kubernetes import client, config

    kubeconfig_path = os.environ.get("KUBECONFIG")
    if kubeconfig_path and os.path.exists(kubeconfig_path):
        try:
            config.load_kube_config(config_file=kubeconfig_path)
        except config.ConfigException as e:
            DEMO_MODE = True
            logger.warning(f"Kubeconfig found but invalid (Windows paths?) — running in DEMO mode: {e}")
    else:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            DEMO_MODE = True
            logger.warning("No Kubernetes config found — running in DEMO mode with synthetic data")

    if not DEMO_MODE:
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
except ImportError:
    DEMO_MODE = True
    logger.warning("kubernetes library not available — running in DEMO mode with synthetic data")

# ---------------------------------------------------------------------------
# Demo / Synthetic Data (for hackathon demo without a live cluster)
# ---------------------------------------------------------------------------
DEMO_PODS = [
    {"name": "checkout-service-7b9f4d6c8-x2k9p", "namespace": "default", "status": "Running", "restarts": 0, "age": "3d", "node": "node-1", "cpu": "120m", "memory": "256Mi"},
    {"name": "checkout-service-7b9f4d6c8-m4n7q", "namespace": "default", "status": "Running", "restarts": 0, "age": "3d", "node": "node-2", "cpu": "95m", "memory": "230Mi"},
    {"name": "payment-service-5c8d3a1b2-j8h5r", "namespace": "default", "status": "CrashLoopBackOff", "restarts": 14, "age": "1d", "node": "node-1", "cpu": "0m", "memory": "0Mi"},
    {"name": "api-gateway-9f2e1d4c7-k3l6w", "namespace": "default", "status": "Running", "restarts": 0, "age": "7d", "node": "node-2", "cpu": "200m", "memory": "512Mi"},
    {"name": "user-service-4a7b2c9d1-p5t8v", "namespace": "default", "status": "Running", "restarts": 2, "age": "5d", "node": "node-1", "cpu": "80m", "memory": "180Mi"},
    {"name": "inventory-service-6d3e8f1a5-n9m2x", "namespace": "default", "status": "Running", "restarts": 0, "age": "7d", "node": "node-3", "cpu": "60m", "memory": "150Mi"},
    {"name": "notification-service-2c5d7e9f3-q4r1s", "namespace": "default", "status": "Running", "restarts": 0, "age": "7d", "node": "node-3", "cpu": "40m", "memory": "100Mi"},
    {"name": "redis-cache-0", "namespace": "default", "status": "Running", "restarts": 0, "age": "14d", "node": "node-2", "cpu": "50m", "memory": "128Mi"},
]

DEMO_DEPLOYMENTS = [
    {"name": "checkout-service", "namespace": "default", "replicas": "2/2", "available": 2, "age": "30d", "image": "myregistry/checkout:v2.3.1"},
    {"name": "payment-service", "namespace": "default", "replicas": "0/1", "available": 0, "age": "30d", "image": "myregistry/payment:v1.8.0"},
    {"name": "api-gateway", "namespace": "default", "replicas": "1/1", "available": 1, "age": "45d", "image": "myregistry/api-gw:v3.1.0"},
    {"name": "user-service", "namespace": "default", "replicas": "1/1", "available": 1, "age": "30d", "image": "myregistry/user:v2.0.5"},
    {"name": "inventory-service", "namespace": "default", "replicas": "1/1", "available": 1, "age": "45d", "image": "myregistry/inventory:v1.5.2"},
    {"name": "notification-service", "namespace": "default", "replicas": "1/1", "available": 1, "age": "45d", "image": "myregistry/notification:v1.2.0"},
]

DEMO_EVENTS = [
    {"type": "Warning", "reason": "BackOff", "object": "pod/payment-service-5c8d3a1b2-j8h5r", "message": "Back-off restarting failed container", "age": "2m", "count": 14},
    {"type": "Warning", "reason": "Unhealthy", "object": "pod/payment-service-5c8d3a1b2-j8h5r", "message": "Liveness probe failed: connection refused on port 8080", "age": "3m", "count": 28},
    {"type": "Normal", "reason": "Pulled", "object": "pod/payment-service-5c8d3a1b2-j8h5r", "message": "Container image 'myregistry/payment:v1.8.0' already present on machine", "age": "5m", "count": 14},
    {"type": "Warning", "reason": "HighMemory", "object": "pod/api-gateway-9f2e1d4c7-k3l6w", "message": "Memory usage at 89% of limit (512Mi)", "age": "10m", "count": 3},
    {"type": "Normal", "reason": "ScalingReplicaSet", "object": "deployment/checkout-service", "message": "Scaled up replica set checkout-service-7b9f4d6c8 to 2", "age": "3d", "count": 1},
]

DEMO_NODES = [
    {"name": "node-1", "status": "Ready", "roles": "worker", "cpu_capacity": "4", "cpu_used": "1.2", "memory_capacity": "8Gi", "memory_used": "4.5Gi", "pods": 3},
    {"name": "node-2", "status": "Ready", "roles": "worker", "cpu_capacity": "4", "cpu_used": "1.8", "memory_capacity": "8Gi", "memory_used": "5.2Gi", "pods": 3},
    {"name": "node-3", "status": "Ready", "roles": "worker", "cpu_capacity": "4", "cpu_used": "0.5", "memory_capacity": "8Gi", "memory_used": "2.1Gi", "pods": 2},
]

DEMO_POD_LOGS = {
    "payment-service": [
        "2026-02-14T01:15:32Z [ERROR] Failed to connect to payment gateway: connection refused",
        "2026-02-14T01:15:32Z [ERROR] Health check failed — port 8080 not responding",
        "2026-02-14T01:15:33Z [INFO] Shutting down gracefully...",
        "2026-02-14T01:15:35Z [INFO] Starting payment-service v1.8.0...",
        "2026-02-14T01:15:35Z [INFO] Loading configuration from /etc/config/payment.yaml",
        "2026-02-14T01:15:36Z [ERROR] FATAL: Cannot read secret 'STRIPE_API_KEY' from vault — permission denied",
        "2026-02-14T01:15:36Z [ERROR] Startup aborted: missing required secrets",
        "2026-02-14T01:15:37Z [INFO] Shutting down gracefully...",
    ],
    "checkout-service": [
        "2026-02-14T01:20:01Z [INFO] Request POST /api/checkout — 200 OK (45ms)",
        "2026-02-14T01:20:02Z [WARN] Downstream payment-service returned 503 — retrying (attempt 1/3)",
        "2026-02-14T01:20:03Z [WARN] Downstream payment-service returned 503 — retrying (attempt 2/3)",
        "2026-02-14T01:20:04Z [ERROR] Downstream payment-service failed after 3 retries — returning 500",
        "2026-02-14T01:20:05Z [INFO] Request POST /api/checkout — 500 Internal Server Error (3012ms)",
        "2026-02-14T01:20:10Z [INFO] Request GET /api/checkout/health — 200 OK (2ms)",
    ],
    "api-gateway": [
        "2026-02-14T01:20:01Z [INFO] Request POST /api/checkout → checkout-service (200, 45ms)",
        "2026-02-14T01:20:05Z [ERROR] Request POST /api/checkout → checkout-service (500, 3012ms)",
        "2026-02-14T01:20:06Z [WARN] High memory usage detected: 456Mi / 512Mi (89%)",
        "2026-02-14T01:20:10Z [INFO] Request GET /health → 200 OK (1ms)",
    ],
}

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "InfraWhisperer K8s Server",
    instructions="Kubernetes cluster management tools for InfraWhisperer. Provides read-only cluster queries and restricted write operations.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


@mcp.tool()
async def list_pods(namespace: str = "default") -> str:
    """List all pods in a Kubernetes namespace with their status, restarts, and resource usage.

    Args:
        namespace: The Kubernetes namespace to query. Defaults to 'default'.

    Returns:
        A formatted table of pods with name, status, restarts, age, node, CPU, and memory.
    """
    if DEMO_MODE:
        pods = [p for p in DEMO_PODS if p["namespace"] == namespace]
        if not pods:
            return f"No pods found in namespace '{namespace}'."
        lines = [f"{'NAME':<50} {'STATUS':<20} {'RESTARTS':<10} {'AGE':<6} {'NODE':<10} {'CPU':<8} {'MEMORY':<8}"]
        lines.append("-" * 112)
        for p in pods:
            lines.append(f"{p['name']:<50} {p['status']:<20} {p['restarts']:<10} {p['age']:<6} {p['node']:<10} {p['cpu']:<8} {p['memory']:<8}")
        return "\n".join(lines)

    ret = v1.list_namespaced_pod(namespace)
    lines = [f"{'NAME':<60} {'STATUS':<18} {'RESTARTS':<10} {'NODE':<20}"]
    lines.append("-" * 108)
    for pod in ret.items:
        restarts = sum(cs.restart_count for cs in (pod.status.container_statuses or []))
        lines.append(f"{pod.metadata.name:<60} {pod.status.phase:<18} {restarts:<10} {(pod.spec.node_name or 'N/A'):<20}")
    return "\n".join(lines) if len(lines) > 2 else f"No pods found in namespace '{namespace}'."


@mcp.tool()
async def get_pod_logs(pod_name: str, namespace: str = "default", lines: int = 50) -> str:
    """Get the most recent log lines from a pod.

    Args:
        pod_name: Name of the pod (can be a partial name — will match the first pod containing this string).
        namespace: The Kubernetes namespace. Defaults to 'default'.
        lines: Number of log lines to return. Defaults to 50.

    Returns:
        The last N log lines from the pod.
    """
    if DEMO_MODE:
        for key, logs in DEMO_POD_LOGS.items():
            if key in pod_name or pod_name in key:
                return f"--- Logs for pod matching '{pod_name}' (last {len(logs)} lines) ---\n" + "\n".join(logs[-lines:])
        return f"No logs found for pod '{pod_name}'. Available pods: {', '.join(DEMO_POD_LOGS.keys())}"

    try:
        log = v1.read_namespaced_pod_log(pod_name, namespace, tail_lines=lines)
        return f"--- Logs for {pod_name} (last {lines} lines) ---\n{log}"
    except client.exceptions.ApiException as e:
        return f"Error fetching logs for {pod_name}: {e.reason}"


@mcp.tool()
async def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """Get detailed information about a specific pod including containers, conditions, and events.

    Args:
        pod_name: Exact name of the pod.
        namespace: The Kubernetes namespace. Defaults to 'default'.

    Returns:
        Detailed pod description including status, containers, conditions, and resource usage.
    """
    if DEMO_MODE:
        for p in DEMO_PODS:
            if p["name"] == pod_name or pod_name in p["name"]:
                desc = {
                    "Name": p["name"],
                    "Namespace": p["namespace"],
                    "Node": p["node"],
                    "Status": p["status"],
                    "Restarts": p["restarts"],
                    "Age": p["age"],
                    "Resources": {"CPU": p["cpu"], "Memory": p["memory"]},
                    "Conditions": [
                        {"Type": "Ready", "Status": "True" if p["status"] == "Running" else "False"},
                        {"Type": "ContainersReady", "Status": "True" if p["status"] == "Running" else "False"},
                    ],
                }
                if p["status"] == "CrashLoopBackOff":
                    desc["LastTermination"] = {
                        "Reason": "Error",
                        "ExitCode": 1,
                        "Message": "Cannot read secret 'STRIPE_API_KEY' from vault — permission denied",
                    }
                return json.dumps(desc, indent=2)
        return f"Pod '{pod_name}' not found in namespace '{namespace}'."

    try:
        pod = v1.read_namespaced_pod(pod_name, namespace)
        info = {
            "Name": pod.metadata.name,
            "Namespace": pod.metadata.namespace,
            "Node": pod.spec.node_name,
            "Status": pod.status.phase,
            "Conditions": [{"Type": c.type, "Status": c.status} for c in (pod.status.conditions or [])],
        }
        return json.dumps(info, indent=2)
    except client.exceptions.ApiException as e:
        return f"Error describing pod {pod_name}: {e.reason}"


@mcp.tool()
async def list_deployments(namespace: str = "default") -> str:
    """List all deployments in a namespace with their replica counts and images.

    Args:
        namespace: The Kubernetes namespace. Defaults to 'default'.

    Returns:
        Formatted table of deployments with name, replicas, available, age, and image.
    """
    if DEMO_MODE:
        deps = [d for d in DEMO_DEPLOYMENTS if d["namespace"] == namespace]
        if not deps:
            return f"No deployments found in namespace '{namespace}'."
        lines = [f"{'NAME':<30} {'REPLICAS':<12} {'AVAILABLE':<12} {'AGE':<8} {'IMAGE':<40}"]
        lines.append("-" * 102)
        for d in deps:
            lines.append(f"{d['name']:<30} {d['replicas']:<12} {d['available']:<12} {d['age']:<8} {d['image']:<40}")
        return "\n".join(lines)

    ret = apps_v1.list_namespaced_deployment(namespace)
    lines = [f"{'NAME':<40} {'READY':<12} {'AVAILABLE':<12}"]
    lines.append("-" * 64)
    for dep in ret.items:
        ready = f"{dep.status.ready_replicas or 0}/{dep.spec.replicas}"
        lines.append(f"{dep.metadata.name:<40} {ready:<12} {dep.status.available_replicas or 0:<12}")
    return "\n".join(lines) if len(lines) > 2 else f"No deployments found in namespace '{namespace}'."


@mcp.tool()
async def get_events(namespace: str = "default", limit: int = 20) -> str:
    """Get recent Kubernetes events in a namespace. Useful for debugging pod issues.

    Args:
        namespace: The Kubernetes namespace. Defaults to 'default'.
        limit: Maximum number of events to return. Defaults to 20.

    Returns:
        Formatted list of recent events with type, reason, object, message, age, and count.
    """
    if DEMO_MODE:
        lines = [f"{'TYPE':<10} {'REASON':<18} {'OBJECT':<50} {'MESSAGE':<60} {'AGE':<6} {'COUNT':<6}"]
        lines.append("-" * 150)
        for e in DEMO_EVENTS[:limit]:
            lines.append(f"{e['type']:<10} {e['reason']:<18} {e['object']:<50} {e['message'][:58]:<60} {e['age']:<6} {e['count']:<6}")
        return "\n".join(lines)

    events = v1.list_namespaced_event(namespace)
    lines = [f"{'TYPE':<10} {'REASON':<20} {'OBJECT':<40} {'MESSAGE':<60}"]
    lines.append("-" * 130)
    for ev in sorted(events.items, key=lambda x: x.last_timestamp or x.metadata.creation_timestamp, reverse=True)[:limit]:
        obj = f"{ev.involved_object.kind}/{ev.involved_object.name}"
        lines.append(f"{ev.type:<10} {ev.reason:<20} {obj:<40} {(ev.message or '')[:58]:<60}")
    return "\n".join(lines)


@mcp.tool()
async def list_nodes() -> str:
    """List all cluster nodes with their status, roles, and resource usage.

    Returns:
        Formatted table of nodes with name, status, roles, CPU usage, memory usage, and pod count.
    """
    if DEMO_MODE:
        lines = [f"{'NAME':<12} {'STATUS':<10} {'ROLES':<10} {'CPU (used/cap)':<18} {'MEM (used/cap)':<20} {'PODS':<6}"]
        lines.append("-" * 76)
        for n in DEMO_NODES:
            cpu = f"{n['cpu_used']}/{n['cpu_capacity']}"
            mem = f"{n['memory_used']}/{n['memory_capacity']}"
            lines.append(f"{n['name']:<12} {n['status']:<10} {n['roles']:<10} {cpu:<18} {mem:<20} {n['pods']:<6}")
        return "\n".join(lines)

    nodes = v1.list_node()
    lines = [f"{'NAME':<30} {'STATUS':<10} {'ROLES':<15}"]
    lines.append("-" * 55)
    for node in nodes.items:
        status = "Ready" if any(c.type == "Ready" and c.status == "True" for c in node.status.conditions) else "NotReady"
        roles = ",".join(k.replace("node-role.kubernetes.io/", "") for k in node.metadata.labels if "node-role" in k) or "worker"
        lines.append(f"{node.metadata.name:<30} {status:<10} {roles:<15}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WRITE TOOLS (Assigned ONLY to Remediation Agent in Archestra)
# ---------------------------------------------------------------------------

@mcp.tool()
async def scale_deployment(name: str, replicas: int, namespace: str = "default") -> str:
    """Scale a deployment to a specified number of replicas.

    ⚠️  RESTRICTED: This tool modifies infrastructure. It is assigned ONLY to the
    Remediation Agent and protected by Dual LLM validation + RBAC (sre-admin role).

    Args:
        name: Name of the deployment to scale.
        replicas: Target number of replicas.
        namespace: The Kubernetes namespace. Defaults to 'default'.

    Returns:
        Confirmation message with previous and new replica count.
    """
    if replicas < 0 or replicas > 50:
        return f"Error: replica count must be between 0 and 50 (got {replicas})."

    if DEMO_MODE:
        for d in DEMO_DEPLOYMENTS:
            if d["name"] == name:
                old = d["replicas"]
                d["replicas"] = f"{replicas}/{replicas}"
                d["available"] = replicas
                return f"✅ Deployment '{name}' scaled: {old} → {replicas}/{replicas}\nTimestamp: {datetime.now(timezone.utc).isoformat()}"
        return f"Error: Deployment '{name}' not found in namespace '{namespace}'."

    try:
        body = {"spec": {"replicas": replicas}}
        apps_v1.patch_namespaced_deployment_scale(name, namespace, body)
        return f"✅ Deployment '{name}' in '{namespace}' scaled to {replicas} replicas.\nTimestamp: {datetime.now(timezone.utc).isoformat()}"
    except client.exceptions.ApiException as e:
        return f"Error scaling deployment: {e.reason}"


@mcp.tool()
async def restart_deployment(name: str, namespace: str = "default") -> str:
    """Perform a rolling restart of a deployment.

    ⚠️  RESTRICTED: This tool modifies infrastructure. It is assigned ONLY to the
    Remediation Agent and protected by Dual LLM validation + RBAC (sre-admin role).

    Args:
        name: Name of the deployment to restart.
        namespace: The Kubernetes namespace. Defaults to 'default'.

    Returns:
        Confirmation message with restart timestamp.
    """
    now = datetime.now(timezone.utc).isoformat()

    if DEMO_MODE:
        for d in DEMO_DEPLOYMENTS:
            if d["name"] == name:
                return f"✅ Deployment '{name}' rolling restart initiated.\nTimestamp: {now}\nAll pods will be recreated with the current configuration."
        return f"Error: Deployment '{name}' not found in namespace '{namespace}'."

    try:
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                    }
                }
            }
        }
        apps_v1.patch_namespaced_deployment(name, namespace, body)
        return f"✅ Deployment '{name}' in '{namespace}' rolling restart initiated.\nTimestamp: {now}"
    except client.exceptions.ApiException as e:
        return f"Error restarting deployment: {e.reason}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"Starting K8s MCP Server (DEMO_MODE={DEMO_MODE})")
    mcp.run(transport="streamable-http")

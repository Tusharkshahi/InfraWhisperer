"""
InfraWhisperer — Database MCP Server
======================================
A Model Context Protocol server for read-only PostgreSQL queries.

🛡️ SECURITY BY DESIGN:
- ONLY SELECT queries are allowed — enforced at the server level
- DML/DDL statements (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE)
  are blocked REGARDLESS of what the agent requests
- Even prompt injection cannot bypass this — the MCP server itself rejects mutations
"""

import json
import logging
import os
import re

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("database-mcp-server")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DEMO_MODE = False

try:
    import psycopg2
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        logger.info("PostgreSQL connection verified.")
    else:
        DEMO_MODE = True
except Exception as e:
    DEMO_MODE = True
    logger.warning(f"PostgreSQL not reachable ({e}) — running in DEMO mode")

if DEMO_MODE:
    logger.warning("Running in DEMO mode with synthetic e-commerce data")

# ---------------------------------------------------------------------------
# SQL Safety
# ---------------------------------------------------------------------------
BLOCKED_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|CALL|COPY|LOAD)\b",
    re.IGNORECASE,
)


def validate_sql(query: str) -> tuple[bool, str]:
    """Validate that a SQL query is read-only (SELECT only).

    Returns:
        (is_safe, error_message) tuple.
    """
    cleaned = query.strip().rstrip(";").strip()

    if not cleaned.upper().startswith("SELECT") and not cleaned.upper().startswith("WITH") and not cleaned.upper().startswith("EXPLAIN"):
        return False, f"❌ BLOCKED: Only SELECT, WITH (CTE), and EXPLAIN queries are allowed. Got: '{cleaned[:50]}...'"

    match = BLOCKED_PATTERNS.search(cleaned)
    if match:
        return False, f"❌ BLOCKED: Detected forbidden keyword '{match.group()}' in query. Only read-only queries are allowed."

    if ";" in cleaned:
        return False, "❌ BLOCKED: Multiple statements detected (semicolon in query body). Only single SELECT statements are allowed."

    return True, ""


# ---------------------------------------------------------------------------
# Demo / Synthetic Data
# ---------------------------------------------------------------------------
DEMO_TABLES = {
    "customers": {
        "columns": [
            {"name": "id", "type": "integer", "nullable": False, "default": "nextval('customers_id_seq')"},
            {"name": "email", "type": "varchar(255)", "nullable": False, "default": None},
            {"name": "name", "type": "varchar(255)", "nullable": False, "default": None},
            {"name": "phone", "type": "varchar(20)", "nullable": True, "default": None},
            {"name": "created_at", "type": "timestamp", "nullable": False, "default": "now()"},
            {"name": "tier", "type": "varchar(20)", "nullable": False, "default": "'standard'"},
        ],
        "row_count": 15234,
    },
    "orders": {
        "columns": [
            {"name": "id", "type": "integer", "nullable": False, "default": "nextval('orders_id_seq')"},
            {"name": "customer_id", "type": "integer", "nullable": False, "default": None},
            {"name": "total_amount", "type": "numeric(10,2)", "nullable": False, "default": None},
            {"name": "status", "type": "varchar(20)", "nullable": False, "default": "'pending'"},
            {"name": "created_at", "type": "timestamp", "nullable": False, "default": "now()"},
            {"name": "payment_id", "type": "varchar(50)", "nullable": True, "default": None},
        ],
        "row_count": 48921,
    },
    "products": {
        "columns": [
            {"name": "id", "type": "integer", "nullable": False, "default": "nextval('products_id_seq')"},
            {"name": "name", "type": "varchar(255)", "nullable": False, "default": None},
            {"name": "price", "type": "numeric(10,2)", "nullable": False, "default": None},
            {"name": "stock", "type": "integer", "nullable": False, "default": "0"},
            {"name": "category", "type": "varchar(100)", "nullable": True, "default": None},
        ],
        "row_count": 1847,
    },
    "order_items": {
        "columns": [
            {"name": "id", "type": "integer", "nullable": False, "default": "nextval('order_items_id_seq')"},
            {"name": "order_id", "type": "integer", "nullable": False, "default": None},
            {"name": "product_id", "type": "integer", "nullable": False, "default": None},
            {"name": "quantity", "type": "integer", "nullable": False, "default": None},
            {"name": "unit_price", "type": "numeric(10,2)", "nullable": False, "default": None},
        ],
        "row_count": 127453,
    },
    "payments": {
        "columns": [
            {"name": "id", "type": "varchar(50)", "nullable": False, "default": None},
            {"name": "order_id", "type": "integer", "nullable": False, "default": None},
            {"name": "amount", "type": "numeric(10,2)", "nullable": False, "default": None},
            {"name": "status", "type": "varchar(20)", "nullable": False, "default": "'pending'"},
            {"name": "provider", "type": "varchar(50)", "nullable": False, "default": "'stripe'"},
            {"name": "created_at", "type": "timestamp", "nullable": False, "default": "now()"},
            {"name": "error_message", "type": "text", "nullable": True, "default": None},
        ],
        "row_count": 48921,
    },
}

DEMO_QUERY_RESULTS = {
    "orders": {
        "columns": ["id", "customer_id", "total_amount", "status", "created_at"],
        "rows": [
            [48921, 1234, 129.99, "pending", "2026-02-14T01:20:00Z"],
            [48920, 5678, 45.50, "pending", "2026-02-14T01:19:30Z"],
            [48919, 9012, 234.00, "failed", "2026-02-14T01:18:45Z"],
            [48918, 3456, 89.99, "failed", "2026-02-14T01:18:00Z"],
            [48917, 7890, 156.75, "failed", "2026-02-14T01:17:30Z"],
        ],
    },
    "failed_payments": {
        "columns": ["payment_id", "order_id", "amount", "status", "error_message", "created_at"],
        "rows": [
            ["pay_err_001", 48919, 234.00, "failed", "Payment gateway timeout — service unavailable", "2026-02-14T01:18:45Z"],
            ["pay_err_002", 48918, 89.99, "failed", "Payment gateway timeout — service unavailable", "2026-02-14T01:18:00Z"],
            ["pay_err_003", 48917, 156.75, "failed", "Payment gateway timeout — service unavailable", "2026-02-14T01:17:30Z"],
            ["pay_err_004", 48916, 67.25, "failed", "Payment gateway timeout — service unavailable", "2026-02-14T01:16:45Z"],
            ["pay_err_005", 48915, 199.99, "failed", "Payment gateway timeout — service unavailable", "2026-02-14T01:16:00Z"],
        ],
    },
    "slow_queries": [
        {"pid": 1234, "duration": "45.2s", "state": "active", "query": "SELECT o.*, c.email FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = 'pending' ORDER BY o.created_at DESC"},
        {"pid": 1235, "duration": "12.8s", "state": "active", "query": "SELECT COUNT(*), status FROM payments WHERE created_at > NOW() - INTERVAL '1 hour' GROUP BY status"},
    ],
}


def _demo_query(query: str) -> str:
    """Process a demo query and return synthetic results."""
    q_upper = query.upper()

    if "PAYMENT" in q_upper and ("FAIL" in q_upper or "ERROR" in q_upper):
        result = DEMO_QUERY_RESULTS["failed_payments"]
    elif "ORDER" in q_upper:
        result = DEMO_QUERY_RESULTS["orders"]
    elif "COUNT" in q_upper:
        return json.dumps({"columns": ["count"], "rows": [[48921]], "row_count": 1}, indent=2)
    else:
        return json.dumps({
            "columns": ["info"],
            "rows": [["Demo mode: synthetic results. Query was parsed and validated as safe."]],
            "query_validated": True,
            "row_count": 1,
        }, indent=2)

    return json.dumps({"columns": result["columns"], "rows": result["rows"], "row_count": len(result["rows"])}, indent=2)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "InfraWhisperer Database Server",
    instructions="Read-only PostgreSQL query tools for InfraWhisperer. All write operations are blocked by design.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


@mcp.tool()
async def run_query(query: str) -> str:
    """Execute a read-only SQL query against the database.

    🛡️ SECURITY: Only SELECT, WITH (CTE), and EXPLAIN queries are allowed.
    INSERT, UPDATE, DELETE, DROP, and all other DML/DDL are blocked at the server level.

    Args:
        query: A SQL SELECT query to execute.

    Returns:
        Query results as JSON with columns and rows.
    """
    is_safe, error = validate_sql(query)
    if not is_safe:
        logger.warning(f"BLOCKED query: {query[:100]}")
        return error

    if DEMO_MODE:
        return _demo_query(query)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to serializable format
        serializable_rows = []
        for row in rows[:100]:  # Limit to 100 rows
            serializable_rows.append([str(v) if not isinstance(v, (int, float, bool, type(None))) else v for v in row])

        return json.dumps({"columns": columns, "rows": serializable_rows, "row_count": len(rows), "truncated": len(rows) > 100}, indent=2)
    except Exception as e:
        return f"Error executing query: {str(e)}"


@mcp.tool()
async def list_tables() -> str:
    """List all tables in the database with their row counts.

    Returns:
        Formatted table of database tables with name, row count, and column count.
    """
    if DEMO_MODE:
        lines = [f"{'TABLE':<25} {'ROWS':<12} {'COLUMNS':<10}"]
        lines.append("-" * 47)
        for name, info in DEMO_TABLES.items():
            lines.append(f"{name:<25} {info['row_count']:<12} {len(info['columns']):<10}")
        return "\n".join(lines)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT schemaname || '.' || relname AS table_name,
                   n_live_tup AS row_count
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        lines = [f"{'TABLE':<40} {'ROWS':<12}"]
        lines.append("-" * 52)
        for row in rows:
            lines.append(f"{row[0]:<40} {row[1]:<12}")
        return "\n".join(lines) if len(lines) > 2 else "No tables found."
    except Exception as e:
        return f"Error listing tables: {str(e)}"


@mcp.tool()
async def describe_table(table_name: str) -> str:
    """Show the schema of a specific table including column names, types, and constraints.

    Args:
        table_name: Name of the table to describe.

    Returns:
        Formatted table schema with column details.
    """
    if DEMO_MODE:
        if table_name not in DEMO_TABLES:
            return f"Table '{table_name}' not found. Available tables: {', '.join(DEMO_TABLES.keys())}"
        table = DEMO_TABLES[table_name]
        lines = [f"Table: {table_name} ({table['row_count']} rows)\n"]
        lines.append(f"{'COLUMN':<20} {'TYPE':<25} {'NULLABLE':<10} {'DEFAULT':<30}")
        lines.append("-" * 85)
        for col in table["columns"]:
            lines.append(f"{col['name']:<20} {col['type']:<25} {'YES' if col['nullable'] else 'NO':<10} {str(col['default'] or ''):<30}")
        return "\n".join(lines)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return f"Table '{table_name}' not found."
        lines = [f"Table: {table_name}\n"]
        lines.append(f"{'COLUMN':<30} {'TYPE':<25} {'NULLABLE':<10} {'DEFAULT':<30}")
        lines.append("-" * 95)
        for row in rows:
            lines.append(f"{row[0]:<30} {row[1]:<25} {row[2]:<10} {str(row[3] or ''):<30}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error describing table: {str(e)}"


@mcp.tool()
async def slow_queries() -> str:
    """Show currently running slow/long-running database queries.

    Returns:
        List of active queries that have been running for more than 5 seconds.
    """
    if DEMO_MODE:
        lines = ["🐌 Slow Queries (running > 5s)\n"]
        for sq in DEMO_QUERY_RESULTS["slow_queries"]:
            lines.append(f"PID: {sq['pid']} | Duration: {sq['duration']} | State: {sq['state']}")
            lines.append(f"  Query: {sq['query'][:100]}...")
            lines.append("")
        return "\n".join(lines)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT pid, now() - pg_stat_activity.query_start AS duration,
                   state, query
            FROM pg_stat_activity
            WHERE state != 'idle'
              AND now() - pg_stat_activity.query_start > interval '5 seconds'
            ORDER BY duration DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return "✅ No slow queries detected (threshold: 5 seconds)."
        lines = ["🐌 Slow Queries (running > 5s)\n"]
        for row in rows:
            lines.append(f"PID: {row[0]} | Duration: {row[1]} | State: {row[2]}")
            lines.append(f"  Query: {row[3][:100]}...")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Error checking slow queries: {str(e)}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"Starting Database MCP Server (DEMO_MODE={DEMO_MODE})")
    mcp.run(transport="streamable-http")

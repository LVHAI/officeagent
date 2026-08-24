import logging
import os
import re
import time
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

SERVICE_NAME = os.getenv("SERVICE_NAME", "enterprise")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "officeagent")
DB_USER = os.getenv("POSTGRES_USER", "officeagent")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "officeagent")

logger = logging.getLogger("app.sql")

# FastMCP 1.11 configures the HTTP bind address/port on the server settings,
# while FastMCP.run() only accepts transport/mount_path. Configure the
# container listener explicitly so Docker can publish port 8000 to the host.
mcp = FastMCP(
    SERVICE_NAME,
    host="0.0.0.0",
    port=8000,
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


def validate_read_only_sql(sql: str) -> str:
    """Allow one PostgreSQL SELECT/WITH statement only."""
    statement = sql.strip()
    if not statement:
        raise ValueError("SQL query must not be empty")

    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if ";" in statement:
        raise ValueError("Only one SQL statement is allowed")

    if not re.match(r"^(SELECT|WITH)\b", statement, flags=re.IGNORECASE):
        raise ValueError("Only SELECT or WITH queries are allowed")

    return statement


def _database_connection() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def _log_sql_start(service: str, tool: str, sql: str, params: list[Any] | None = None) -> float:
    """Log the SQL before execution and return a monotonic start timestamp."""
    started = time.monotonic()
    logger.info(
        "sql.execute.start service=%s tool=%s sql=%s params=%r",
        service,
        tool,
        sql,
        params,
    )
    return started


def _log_sql_completed(
    service: str,
    tool: str,
    sql: str,
    started: float,
    row_count: int,
    params: list[Any] | None = None,
) -> None:
    logger.info(
        "sql.execute.completed service=%s tool=%s elapsed_ms=%.2f row_count=%d sql=%s params=%r",
        service,
        tool,
        (time.monotonic() - started) * 1000,
        row_count,
        sql,
        params,
    )


def _log_sql_failed(
    service: str,
    tool: str,
    sql: str,
    started: float,
    error: Exception,
    params: list[Any] | None = None,
) -> None:
    logger.exception(
        "sql.execute.failed service=%s tool=%s elapsed_ms=%.2f sql=%s params=%r error=%s",
        service,
        tool,
        (time.monotonic() - started) * 1000,
        sql,
        params,
        error,
    )


async def _sql_query(sql: str, limit: int = 100) -> dict[str, Any]:
    statement = validate_read_only_sql(sql)
    limit = max(1, min(limit, 500))
    started = _log_sql_start("database", "sql_query", statement)

    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(statement)
                columns = [description.name for description in cursor.description or []]
                rows = cursor.fetchmany(limit)
    except Exception as error:
        _log_sql_failed("database", "sql_query", statement, started, error)
        raise

    _log_sql_completed("database", "sql_query", statement, started, len(rows))
    return {
        "system": "PostgreSQL",
        "database": DB_NAME,
        "tool": "sql_query",
        "sql": statement,
        "columns": columns,
        "rows": [dict(zip(columns, row, strict=True)) for row in rows],
        "row_count": len(rows),
        "limit": limit,
    }


def build_service_tools(service_name: str, server: FastMCP | None = None) -> list[Any]:
    """Return only the tools belonging to the selected MCP service."""
    server = server or mcp

    if service_name == "database":

        @server.tool(name="sql_query")
        async def sql_query(sql: str, limit: int = 100) -> dict[str, Any]:
            """Execute one bounded read-only SQL query against PostgreSQL."""
            return await _sql_query(sql, limit)

        return [sql_query]

    if service_name == "crm":

        @server.tool(name="customer_query")
        async def customer_query(region: str | None = None) -> dict[str, Any]:
            """Compatibility CRM query backed by PostgreSQL customer data."""
            clauses = []
            params: list[Any] = []
            if region:
                clauses.append("region = %s")
                params.append(region)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"""
                SELECT customer_id, name, email, region, level, total_spent,
                       last_purchase_at, created_at
                FROM customers
                {where}
                ORDER BY total_spent DESC
                LIMIT 100
            """
            started = _log_sql_start("crm", "customer_query", sql, params)
            try:
                with _database_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION READ ONLY")
                        cursor.execute(sql, params)
                        columns = [description.name for description in cursor.description or []]
                        rows = cursor.fetchall()
            except Exception as error:
                _log_sql_failed("crm", "customer_query", sql, started, error, params)
                raise

            _log_sql_completed("crm", "customer_query", sql, started, len(rows), params)
            return {
                "system": "CRM",
                "database": DB_NAME,
                "tool": "customer_query",
                "region": region,
                "rows": [dict(zip(columns, row, strict=True)) for row in rows],
                "row_count": len(rows),
            }

        return [customer_query]

    if service_name == "knowledge":

        @server.tool()
        def knowledge_search(query: str) -> dict[str, Any]:
            return {
                "system": "Knowledge",
                "api": "knowledge.search",
                "query": query,
                "sources": [],
            }

        return [knowledge_search]

    if service_name == "report":

        @server.tool()
        def report_generate(title: str, content: str) -> dict[str, Any]:
            return {
                "system": "Report",
                "api": "report.generate",
                "title": title,
                "content": content,
            }

        return [report_generate]

    return []


# Register only the tools for this container's SERVICE_NAME. This prevents the
# four MCP endpoints from exposing duplicate cross-domain tools.
SERVICE_TOOLS = build_service_tools(SERVICE_NAME)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

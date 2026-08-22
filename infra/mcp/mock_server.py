import os

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

# FastMCP 1.11 configures the HTTP bind address/port on the server settings,
# while FastMCP.run() only accepts transport/mount_path.  Configure the
# container listener explicitly so Docker can publish port 8000 to the host.
mcp = FastMCP(
    os.getenv("SERVICE_NAME", "enterprise"),
    host="0.0.0.0",
    port=8000,
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


@mcp.tool()
def customer_query(region: str | None = None) -> dict:
    return {
        "system": "CRM",
        "api": "customer.query",
        "region": region,
        "customers": [
            {"id": "C001", "region": "East China", "status": "active", "value": 120000},
            {"id": "C002", "region": "East China", "status": "churned", "value": 45000},
        ],
    }


@mcp.tool()
def sales_summary(region: str | None = None) -> dict:
    return {
        "system": "ERP",
        "api": "sales.summary",
        "region": region,
        "revenue": 165000,
        "orders": 42,
    }


@mcp.tool()
def knowledge_search(query: str) -> dict:
    return {
        "system": "Knowledge",
        "api": "knowledge.search",
        "query": query,
        "sources": [],
    }


@mcp.tool()
def report_generate(title: str, content: str) -> dict:
    return {
        "system": "Report",
        "api": "report.generate",
        "title": title,
        "content": content,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

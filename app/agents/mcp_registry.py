from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.agents.mcp_client import MCPClient, MCPTool
from app.agents.mcp_transport import streamable_http_transport
from app.core.config import settings

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """Own MCP clients and keep concrete enterprise tool schemas out of Agent context."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, list[StructuredTool]] = {}
        self._errors: dict[str, str] = {}

    async def initialize(self) -> None:
        services = {
            "crm": settings.crm_mcp_url,
            "database": settings.database_mcp_url,
            "knowledge": settings.knowledge_mcp_url,
            "report": settings.report_mcp_url,
        }
        for service, url in services.items():
            client = MCPClient(_HttpTransport(url))
            self._clients[service] = client

            # Knowledge tools are deterministic infrastructure used directly by the
            # Knowledge Agent. Enterprise business tools remain undiscovered until
            # a selected Skill explicitly requests dynamic discovery.
            if service != "knowledge":
                logger.info("mcp.client.ready service=%s dynamic_discovery=true", service)
                continue

            started = time.perf_counter()
            logger.info("mcp.discovery.start service=%s url=%s", service, url)
            try:
                definitions = await client.discover_tools()
                self._tools[service] = build_langchain_tools(client, definitions)
                logger.info(
                    "mcp.discovery.completed service=%s tools=%d elapsed_ms=%.1f",
                    service,
                    len(definitions),
                    (time.perf_counter() - started) * 1000,
                )
            except Exception as exc:  # noqa: BLE001 - discovery failure is isolated per MCP
                self._tools[service] = []
                self._errors[service] = str(exc)
                logger.exception(
                    "mcp.discovery.failed service=%s elapsed_ms=%.1f",
                    service,
                    (time.perf_counter() - started) * 1000,
                )

    def get_client(self, service: str) -> MCPClient:
        try:
            return self._clients[service]
        except KeyError as exc:
            raise KeyError(f"Unknown or uninitialized MCP service: {service}") from exc

    async def discover_skill_tools(self, service: str, allowed_tools: tuple[str, ...]) -> list[MCPTool]:
        """Discover only the MCP schema required by a selected Skill."""
        client = self.get_client(service)
        started = time.perf_counter()
        logger.info(
            "mcp.skill.discovery.start service=%s allowed_tools=%s",
            service,
            list(allowed_tools),
        )
        definitions = await client.discover_tools()
        allowed = set(allowed_tools)
        selected = [definition for definition in definitions if definition.name in allowed]
        logger.info(
            "mcp.skill.discovery.completed service=%s discovered=%d selected=%d elapsed_ms=%.1f",
            service,
            len(definitions),
            len(selected),
            (time.perf_counter() - started) * 1000,
        )
        return selected

    def tools(self, *services: str) -> list[StructuredTool]:
        selected = services or tuple(self._tools)
        return [tool for service in selected for tool in self._tools.get(service, [])]

    @property
    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    async def close(self) -> None:
        self._clients.clear()
        self._tools.clear()
        self._errors.clear()


class _HttpTransport:
    """MCPTransport adapter that opens a short-lived Streamable HTTP session per call."""

    def __init__(self, url: str):
        self.url = url

    async def list_tools(self) -> Any:
        async with streamable_http_transport(self.url) as session:
            return await session.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        async with streamable_http_transport(self.url) as session:
            return await session.call_tool(name, arguments)


def _schema_model(tool: MCPTool):
    properties = tool.input_schema.get("properties", {})
    required = set(tool.input_schema.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for name, spec in properties.items():
        json_type = spec.get("type", "string")
        python_type: Any = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict[str, Any],
            "array": list[Any],
        }.get(json_type, Any)
        default = ... if name in required else spec.get("default")
        fields[name] = (python_type, default)
    return create_model(f"{tool.name.replace('.', '_')}Args", **fields)


def _log_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """Log the concrete SQL for database queries without dumping all tool arguments."""
    if tool_name != "sql_query":
        return

    sql = arguments.get("sql") or arguments.get("query")
    if sql is None:
        logger.warning(
            "mcp.sql.query.missing_sql tool=%s argument_keys=%s",
            tool_name,
            sorted(arguments.keys()),
        )
        return

    logger.info("mcp.sql.query tool=%s sql=%s", tool_name, str(sql).strip())


def build_langchain_tools(client: MCPClient, definitions: list[MCPTool]) -> list[StructuredTool]:
    result: list[StructuredTool] = []
    for definition in definitions:
        async def invoke(_definition=definition, **kwargs: Any):
            started = time.perf_counter()
            logger.info("mcp.tool.invoke.start tool=%s", _definition.name)
            _log_tool_arguments(_definition.name, kwargs)
            try:
                result = await client.call(_definition.name, kwargs)
                logger.info(
                    "mcp.tool.invoke.completed tool=%s elapsed_ms=%.1f",
                    _definition.name,
                    (time.perf_counter() - started) * 1000,
                )
                return result
            except asyncio.CancelledError:
                logger.warning("mcp.tool.invoke.cancelled tool=%s", _definition.name)
                raise
            except Exception as exc:  # noqa: BLE001 - tool failures are surfaced to the agent
                logger.exception(
                    "mcp.tool.invoke.failed tool=%s elapsed_ms=%.1f error=%s",
                    _definition.name,
                    (time.perf_counter() - started) * 1000,
                    exc,
                )
                raise

        result.append(
            StructuredTool.from_function(
                coroutine=invoke,
                name=definition.name.replace(".", "_"),
                description=definition.description or f"MCP tool: {definition.name}",
                args_schema=_schema_model(definition),
            )
        )
    return result


mcp_registry = MCPToolRegistry()

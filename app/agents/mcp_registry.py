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
    """Discover MCP tools once at startup and expose safe LangChain wrappers."""

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

    def __init__(self, url: str) -> None:
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


def build_langchain_tools(client: MCPClient, definitions: list[MCPTool]) -> list[StructuredTool]:
    result: list[StructuredTool] = []
    for definition in definitions:
        async def invoke(_definition=definition, **kwargs: Any):
            started = time.perf_counter()
            logger.info("mcp.tool.invoke.start tool=%s", _definition.name)
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

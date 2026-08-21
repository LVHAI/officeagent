from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator
from uuid import uuid4

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.retry import retry_async
from app.core.trace import ToolSource


@dataclass(frozen=True)
class MCPServer:
    name: str
    url: str
    timeout_seconds: float = 15.0
    failure_threshold: int = 3
    recovery_seconds: float = 30.0


class CircuitOpenError(RuntimeError):
    """下游 MCP 服务连续失败后暂时熔断。"""


class MCPClient:
    """MCP 客户端：统一处理连接、超时、重试、熔断和工具来源追踪。"""

    def __init__(self, server: MCPServer) -> None:
        self.server = server
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def _before_call(self) -> None:
        async with self._lock:
            if self._opened_at is None:
                return
            if time.monotonic() - self._opened_at < self.server.recovery_seconds:
                raise CircuitOpenError(f"MCP server {self.server.name!r} circuit is open")
            # 到恢复窗口后允许一次探测请求。
            self._opened_at = None

    async def _record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.server.failure_threshold:
                self._opened_at = time.monotonic()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        # 每次建立独立会话，避免不同 Agent 之间共享连接造成状态污染。
        await self._before_call()
        try:
            async with streamable_http_client(self.server.url) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await retry_async(
                        lambda: asyncio.wait_for(client.initialize(), timeout=self.server.timeout_seconds),
                        retries=2,
                    )
                    yield client
            await self._record_success()
        except Exception:
            await self._record_failure()
            raise

    async def list_tools(self) -> list[dict[str, Any]]:
        # Tool Discovery 只返回 Agent 路由所需的元数据，不在这里执行工具。
        started = time.monotonic()
        request_id = str(uuid4())
        async with self.session() as client:
            result = await retry_async(
                lambda: asyncio.wait_for(client.list_tools(), timeout=self.server.timeout_seconds),
                retries=2,
            )
        elapsed = int((time.monotonic() - started) * 1000)
        source = ToolSource(
            system=self.server.name,
            mcp_server=self.server.name,
            tool="__discovery__",
            request_id=request_id,
            execution_time_ms=elapsed,
        )
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
                "server": self.server.name,
                "source": source.__dict__,
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        # MCP 调用设置独立超时；失败会进入统一 retry 和 circuit breaker 策略。
        started = time.monotonic()
        request_id = str(uuid4())
        async with self.session() as client:
            result = await retry_async(
                lambda: asyncio.wait_for(
                    client.call_tool(name, arguments or {}),
                    timeout=self.server.timeout_seconds,
                ),
                retries=2,
            )
        # MCP SDK 返回对象保留原始结构，调用方可继续读取 structured content。
        if isinstance(result, dict):
            result.setdefault(
                "source",
                ToolSource(
                    system=self.server.name,
                    mcp_server=self.server.name,
                    tool=name,
                    request_id=request_id,
                    execution_time_ms=int((time.monotonic() - started) * 1000),
                ).__dict__,
            )
        return result

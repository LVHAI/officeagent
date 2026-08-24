from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.mcp.client import MCPClient, MCPError, MCPTool


class CircuitOpenError(MCPError):
    """目标 MCP 连续失败后进入熔断状态。"""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 15.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.recovery_timeout:
            # 半开状态：允许下一次请求探测服务是否恢复。
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


class ResilientMCPClient:
    """为 MCP Client 增加有界重试、指数退避、熔断和取消传播。"""

    def __init__(
        self,
        client: MCPClient,
        *,
        max_retries: int = 2,
        base_delay: float = 0.2,
        max_delay: float = 2.0,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.client = client
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.breaker = breaker or CircuitBreaker()

    async def _execute(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        if not self.breaker.allow():
            raise CircuitOpenError(f"MCP circuit is open: {self.client.server}")

        for attempt in range(self.max_retries + 1):
            try:
                result = await operation()
                self.breaker.success()
                return result
            except asyncio.CancelledError:
                # Cancellation 必须立即向上游传播，不能被重试吞掉。
                raise
            except MCPError:
                self.breaker.failure()
                if attempt >= self.max_retries:
                    raise
                delay = min(self.max_delay, self.base_delay * (2**attempt))
                # Full jitter 避免多个并发 Agent 同时重试形成惊群。
                await asyncio.sleep(random.uniform(0, delay))

        raise AssertionError("unreachable")

    async def list_tools(self) -> list[MCPTool]:
        return await self._execute(self.client.list_tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._execute(lambda: self.client.call_tool(name, arguments))

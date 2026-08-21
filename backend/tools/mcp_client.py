"""
MCP Client 基础抽象。

当前提供客户端生命周期接口，后续可以接入标准 MCP SDK。
"""

from typing import Any, Dict


class MCPClient:
    """MCP 服务调用客户端。"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def call(self, method: str, params: Dict[str, Any]):
        """调用 MCP 方法。

        生产环境这里接入实际网络请求，需要结合：
        - timeout
        - retry
        - circuit breaker
        """
        return {
            "method": method,
            "params": params,
            "endpoint": self.endpoint,
        }

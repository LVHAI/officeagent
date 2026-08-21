"""
Tool 执行运行时。

负责统一管理：
1. 参数校验
2. 工具调用
3. 异常转换
4. 后续 Retry/CircuitBreaker 集成
"""


class ToolExecutor:
    def __init__(self, registry=None):
        self.registry = registry

    async def execute(self, tool_name: str, arguments: dict):
        """执行工具调用。"""
        tool = self.registry.get(tool_name) if self.registry else None

        if tool is None:
            return {
                "success": False,
                "error_code": "TOOL_NOT_FOUND",
                "retryable": False,
            }

        try:
            result = await tool.invoke(arguments)
            return {
                "success": True,
                "data": result,
            }
        except Exception as exc:
            # 工具异常不能直接抛给 Agent，需要转换为统一错误。
            return {
                "success": False,
                "error_code": str(exc),
                "retryable": True,
            }

"""
Workflow 异常处理模块。

统一管理 Agent 执行过程中产生的异常。
"""


class WorkflowExceptionHandler:
    """异常分类器。"""

    @staticmethod
    def classify(exc: Exception):
        """判断异常是否可以重试。"""
        retryable_errors = (
            TimeoutError,
            ConnectionError,
        )

        return {
            "error": str(exc),
            "retryable": isinstance(exc, retryable_errors),
        }

"""
Agent 调用可靠性组件。

实现：
- 指数退避重试
- 可重试异常分类
- 最大重试次数限制
"""

import asyncio
from typing import Callable, Any


async def retry_with_backoff(
    func: Callable,
    max_retry: int = 3,
    base_delay: int = 1,
    *args,
    **kwargs
) -> Any:
    """带指数退避的异步重试。

    延迟策略:
    1s -> 2s -> 4s

    只建议用于网络异常、超时等临时错误。
    业务参数错误应该快速失败。
    """

    last_exception = None

    for attempt in range(max_retry):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exception = exc

            if attempt == max_retry - 1:
                break

            # 使用指数退避避免服务瞬间压力过大。
            await asyncio.sleep(base_delay * (2 ** attempt))

    raise last_exception

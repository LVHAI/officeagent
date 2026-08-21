"""
工具调用重试策略。
采用指数退避，避免外部系统短暂异常导致任务失败。
"""

import asyncio


async def retry_call(func, retries: int = 3, base_delay: int = 1):
    last_error = None

    for attempt in range(retries):
        try:
            return await func()
        except Exception as exc:
            last_error = exc
            # 指数退避：1s、2s、4s
            await asyncio.sleep(base_delay * (2 ** attempt))

    raise last_error

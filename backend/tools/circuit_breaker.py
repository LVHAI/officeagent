"""
工具熔断器。
防止外部 MCP 服务异常时造成 Agent 雪崩。
"""

import time


class CircuitBreaker:
    def __init__(self, threshold=5, timeout=60):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.open_time = None

    def allow_request(self):
        if self.open_time is None:
            return True

        # 超过恢复时间后允许探测恢复
        return time.time() - self.open_time > self.timeout

    def success(self):
        self.failures = 0
        self.open_time = None

    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_time = time.time()

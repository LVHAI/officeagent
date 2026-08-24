from __future__ import annotations

import socket
from dataclasses import dataclass

from app.core.config import Settings, settings


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ok: bool
    detail: str


def _tcp_check(host: str, port: int, name: str) -> DependencyStatus:
    # 这里只做轻量 TCP 探活，避免健康检查本身阻塞业务请求。
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return DependencyStatus(name, True, "reachable")
    except OSError as exc:
        return DependencyStatus(name, False, str(exc))


def dependency_status(current: Settings = settings) -> list[DependencyStatus]:
    # Backend 在 Mac 本机运行，因此通过 localhost 检查 Docker 暴露出来的基础设施端口。
    return [
        _tcp_check(current.postgres_host, current.postgres_port, "postgres"),
        _tcp_check(current.redis_host, current.redis_port, "redis"),
        _tcp_check(current.milvus_host, current.milvus_port, "milvus"),
    ]

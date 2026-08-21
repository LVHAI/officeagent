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
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return DependencyStatus(name, True, "reachable")
    except OSError as exc:
        return DependencyStatus(name, False, str(exc))


def dependency_status(current: Settings = settings) -> list[DependencyStatus]:
    return [
        _tcp_check(current.postgres_host, current.postgres_port, "postgres"),
        _tcp_check(current.redis_host, current.redis_port, "redis"),
        _tcp_check(current.milvus_host, current.milvus_port, "milvus"),
    ]

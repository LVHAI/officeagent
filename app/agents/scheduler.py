from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.agents.execution_plan import ExecutionTask

logger = logging.getLogger(__name__)


async def execute_with_dependencies(
    tasks: list[ExecutionTask],
    execute: Callable[[ExecutionTask], Awaitable[tuple[dict, dict]]],
    *,
    max_parallel: int,
) -> list[tuple[dict, dict]]:
    """Execute a plan respecting depends_on while preserving bounded concurrency.

    Tasks without dependencies form the first wave. A dependent task is released
    only after every dependency completes successfully. If a dependency fails,
    the dependent task is marked blocked instead of executing with incomplete
    context. Independent branches continue running.
    """
    by_id = {task.task_id: task for task in tasks}
    completed: dict[str, tuple[dict, dict]] = {}
    failed: set[str] = set()
    pending = set(by_id)
    results: dict[str, tuple[dict, dict]] = {}
    semaphore = asyncio.Semaphore(max_parallel)

    while pending:
        ready: list[ExecutionTask] = []
        blocked: list[ExecutionTask] = []

        for task_id in pending:
            task = by_id[task_id]
            deps = set(task.depends_on)
            if deps & failed:
                blocked.append(task)
            elif deps <= completed.keys():
                ready.append(task)

        for task in blocked:
            pending.remove(task.task_id)
            error = f"blocked by failed dependency: {sorted(set(task.depends_on) & failed)}"
            output = {
                "agent_id": task.agent,
                "status": "failed",
                "result": None,
                "sources": [],
                "errors": [error],
                "traces": [],
                "elapsed_ms": 0.0,
            }
            delegation = {
                "task_id": task.task_id,
                "delegation_id": task.task_id,
                "parent_agent_id": "supervisor",
                "child_agent_id": task.agent,
                "status": "blocked",
                "reason": task.query,
                "elapsed_ms": 0.0,
                "error": error,
            }
            results[task.task_id] = (output, delegation)
            failed.add(task.task_id)
            logger.warning("workflow.task.blocked execution_task_id=%s error=%s", task.task_id, error)

        if not ready:
            if pending:
                unresolved = sorted(pending)
                error = f"execution plan contains unresolved dependency cycle: {unresolved}"
                raise ValueError(error)
            break

        async def run(task: ExecutionTask) -> tuple[str, tuple[dict, dict]]:
            async with semaphore:
                return task.task_id, await execute(task)

        wave = await asyncio.gather(*(run(task) for task in ready))
        for task_id, result in wave:
            pending.remove(task_id)
            results[task_id] = result
            output = result[0]
            if output.get("status") == "completed":
                completed[task_id] = result
            else:
                failed.add(task_id)

    return [results[task.task_id] for task in tasks]

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
    """Execute a plan with bounded concurrency and explicit dependency context.

    Hard dependencies block a task when a dependency fails. A task may opt into
    ``constraints.dependency_mode=soft`` to receive successful and failed dependency
    results as partial context instead of being blocked. Dependency results are
    copied into the task constraints before execution so downstream agents can use
    upstream evidence without hidden global state.
    """
    if max_parallel <= 0:
        raise ValueError("max_parallel must be positive")

    by_id = {task.task_id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("execution plan contains duplicate task_id")

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
            mode = str(task.constraints.get("dependency_mode", "hard"))
            failed_deps = deps & failed
            if failed_deps and mode != "soft":
                blocked.append(task)
            elif deps <= completed.keys() or (failed_deps and mode == "soft" and failed_deps <= failed):
                dependency_results = {
                    dep_id: {
                        "status": results[dep_id][0].get("status"),
                        "result": results[dep_id][0].get("result"),
                        "errors": results[dep_id][0].get("errors", []),
                    }
                    for dep_id in deps
                    if dep_id in results
                }
                ready.append(
                    task.model_copy(
                        update={
                            "constraints": {
                                **task.constraints,
                                "dependency_results": dependency_results,
                            }
                        }
                    )
                )

        for task in blocked:
            pending.remove(task.task_id)
            failed_deps = sorted(set(task.depends_on) & failed)
            error = f"blocked by failed dependency: {failed_deps}"
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
                raise ValueError(f"execution plan contains unresolved dependency cycle: {unresolved}")
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

import asyncio

import pytest

from app.agents.execution_plan import ExecutionTask
from app.agents.scheduler import execute_with_dependencies


@pytest.mark.asyncio
async def test_independent_tasks_run_in_parallel():
    started = {}
    release = asyncio.Event()

    async def execute(task):
        started[task.task_id] = asyncio.get_running_loop().time()
        if len(started) == 2:
            release.set()
        await release.wait()
        return ({"status": "completed", "result": task.task_id}, {"task": task.task_id})

    tasks = [
        ExecutionTask(task_id="k", agent="knowledge-agent", query="k"),
        ExecutionTask(task_id="w", agent="web-agent", query="w"),
    ]
    results = await execute_with_dependencies(tasks, execute, max_parallel=2)
    assert [item[0]["status"] for item in results] == ["completed", "completed"]
    assert abs(started["k"] - started["w"]) < 0.1


@pytest.mark.asyncio
async def test_hard_failed_dependency_blocks_downstream_task():
    called = []

    async def execute(task):
        called.append(task.task_id)
        if task.task_id == "a":
            return ({"status": "failed", "result": None, "errors": ["boom"]}, {})
        return ({"status": "completed", "result": "ok"}, {})

    tasks = [
        ExecutionTask(task_id="a", agent="tool-agent", query="a"),
        ExecutionTask(task_id="b", agent="knowledge-agent", query="b", depends_on=["a"]),
    ]
    results = await execute_with_dependencies(tasks, execute, max_parallel=2)
    assert called == ["a"]
    assert results[1][0]["status"] == "failed"
    assert "blocked by failed dependency" in results[1][0]["errors"][0]


@pytest.mark.asyncio
async def test_soft_dependency_receives_upstream_result():
    received = {}

    async def execute(task):
        received[task.task_id] = task.constraints.get("dependency_results")
        return ({"status": "completed", "result": task.task_id}, {})

    tasks = [
        ExecutionTask(task_id="a", agent="tool-agent", query="a"),
        ExecutionTask(
            task_id="b",
            agent="knowledge-agent",
            query="b",
            depends_on=["a"],
            constraints={"dependency_mode": "soft"},
        ),
    ]
    await execute_with_dependencies(tasks, execute, max_parallel=2)
    assert received["b"]["a"]["status"] == "completed"

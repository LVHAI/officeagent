import asyncio

import pytest

from app.agents.execution_plan import ExecutionTask
from app.agents.scheduler import execute_with_dependencies


@pytest.mark.asyncio
async def test_independent_tasks_run_in_same_wave():
    order: list[str] = []
    tasks = [
        ExecutionTask(task_id="a", agent="tool-agent", query="a"),
        ExecutionTask(task_id="b", agent="web-agent", query="b"),
    ]

    async def execute(task: ExecutionTask):
        order.append(f"start:{task.task_id}")
        await asyncio.sleep(0)
        order.append(f"end:{task.task_id}")
        return ({"agent_id": task.agent, "status": "completed", "errors": [], "traces": []}, {})

    results = await execute_with_dependencies(tasks, execute, max_parallel=2)

    assert [item[0]["status"] for item in results] == ["completed", "completed"]
    assert set(order[:2]) == {"start:a", "start:b"}


@pytest.mark.asyncio
async def test_dependent_task_waits_for_dependency():
    order: list[str] = []
    tasks = [
        ExecutionTask(task_id="db", agent="tool-agent", query="db"),
        ExecutionTask(task_id="web", agent="web-agent", query="web", depends_on=["db"]),
    ]

    async def execute(task: ExecutionTask):
        order.append(f"start:{task.task_id}")
        await asyncio.sleep(0)
        order.append(f"end:{task.task_id}")
        return ({"agent_id": task.agent, "status": "completed", "errors": [], "traces": []}, {})

    await execute_with_dependencies(tasks, execute, max_parallel=2)

    assert order.index("end:db") < order.index("start:web")


@pytest.mark.asyncio
async def test_dependent_task_receives_dependency_results():
    received: dict[str, object] = {}
    tasks = [
        ExecutionTask(task_id="db", agent="tool-agent", query="db"),
        ExecutionTask(task_id="web", agent="web-agent", query="web", depends_on=["db"]),
    ]

    async def execute(task: ExecutionTask):
        dependency_results = task.constraints.get("dependency_results")
        if task.task_id == "web":
            received["dependency_results"] = dependency_results
        return (
            {
                "agent_id": task.agent,
                "status": "completed",
                "result": {"rows": [1, 2]},
                "errors": [],
                "traces": [],
            },
            {},
        )

    await execute_with_dependencies(tasks, execute, max_parallel=2)

    assert received["dependency_results"] == {"db": {"rows": [1, 2]}}


@pytest.mark.asyncio
async def test_soft_dependency_runs_with_partial_dependency_results():
    called: list[str] = []
    tasks = [
        ExecutionTask(task_id="bad", agent="tool-agent", query="bad"),
        ExecutionTask(
            task_id="web",
            agent="web-agent",
            query="web",
            depends_on=["bad"],
            constraints={"dependency_mode": "soft"},
        ),
    ]

    async def execute(task: ExecutionTask):
        called.append(task.task_id)
        status = "failed" if task.task_id == "bad" else "completed"
        return (
            {"agent_id": task.agent, "status": status, "result": None, "errors": ["boom"] if status == "failed" else [], "traces": []},
            {},
        )

    results = await execute_with_dependencies(tasks, execute, max_parallel=2)

    assert called == ["bad", "web"]
    assert results[1][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_failed_dependency_blocks_dependent_but_not_independent_branch():
    called: list[str] = []
    tasks = [
        ExecutionTask(task_id="bad", agent="tool-agent", query="bad"),
        ExecutionTask(task_id="blocked", agent="web-agent", query="blocked", depends_on=["bad"]),
        ExecutionTask(task_id="independent", agent="knowledge-agent", query="independent"),
    ]

    async def execute(task: ExecutionTask):
        called.append(task.task_id)
        status = "failed" if task.task_id == "bad" else "completed"
        errors = [] if status == "completed" else ["boom"]
        return (
            {"agent_id": task.agent, "status": status, "errors": errors, "traces": []},
            {},
        )

    results = await execute_with_dependencies(tasks, execute, max_parallel=2)

    assert called == ["bad", "independent"]
    assert results[1][0]["status"] == "failed"
    assert "blocked by failed dependency" in results[1][0]["errors"][0]


@pytest.mark.asyncio
async def test_cycle_is_rejected():
    tasks = [
        ExecutionTask(task_id="a", agent="tool-agent", query="a", depends_on=["b"]),
        ExecutionTask(task_id="b", agent="web-agent", query="b", depends_on=["a"]),
    ]

    async def execute(task: ExecutionTask):
        return ({"agent_id": task.agent, "status": "completed", "errors": [], "traces": []}, {})

    with pytest.raises(ValueError, match="unresolved dependency cycle"):
        await execute_with_dependencies(tasks, execute, max_parallel=2)

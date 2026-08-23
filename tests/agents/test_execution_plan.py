import pytest

from app.agents.execution_plan import ExecutionPlan


def test_execution_plan_accepts_independent_parallel_tasks():
    plan = ExecutionPlan(
        tasks=[
            {"task_id": "k1", "agent": "knowledge-agent", "query": "查制度", "parallel_group": "a"},
            {"task_id": "w1", "agent": "web-agent", "query": "查最新趋势", "parallel_group": "a"},
        ]
    )
    assert len(plan.tasks) == 2


def test_execution_plan_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate task_id"):
        ExecutionPlan(
            tasks=[
                {"task_id": "x", "agent": "knowledge-agent", "query": "a"},
                {"task_id": "x", "agent": "web-agent", "query": "b"},
            ]
        )


def test_execution_plan_rejects_unknown_dependency():
    with pytest.raises(ValueError, match="unknown tasks"):
        ExecutionPlan(
            tasks=[
                {
                    "task_id": "x",
                    "agent": "tool-agent",
                    "query": "查询客户",
                    "depends_on": ["missing"],
                }
            ]
        )

import pytest

from app.agents.execution_plan import ExecutionPlan, ExecutionPlanInput, ExecutionTask


def test_execution_plan_normalizes_nullable_optional_fields():
    plan = ExecutionPlanInput(
        tasks=[
            {
                "task_id": "k1",
                "agent": "knowledge-agent",
                "query": "查询制度",
                "depends_on": None,
                "parallel_group": None,
                "constraints": None,
            }
        ],
        rationale=None,
    ).to_execution_plan()
    task = plan.tasks[0]
    assert task.depends_on == []
    assert task.parallel_group == "default"
    assert task.constraints == {}
    assert plan.rationale == ""


def test_execution_plan_rejects_duplicate_and_unknown_dependencies():
    with pytest.raises(ValueError, match="duplicate task_id"):
        ExecutionPlan(
            tasks=[
                ExecutionTask(task_id="a", agent="tool-agent", query="x"),
                ExecutionTask(task_id="a", agent="web-agent", query="y"),
            ]
        )

    with pytest.raises(ValueError, match="unknown tasks"):
        ExecutionPlan(
            tasks=[
                ExecutionTask(task_id="a", agent="tool-agent", query="x", depends_on=["missing"])
            ]
        )


def test_execution_plan_rejects_self_dependency():
    with pytest.raises(ValueError, match="cannot depend on itself"):
        ExecutionPlan(
            tasks=[ExecutionTask(task_id="a", agent="tool-agent", query="x", depends_on=["a"])]
        )

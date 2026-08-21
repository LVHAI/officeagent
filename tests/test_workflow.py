import pytest

from officeagent.workflow.graph import WorkflowGraph
from officeagent.workflow.state import WorkflowState


@pytest.mark.asyncio
async def test_workflow_node_execution():
    """验证工作流节点可以正常执行。"""
    graph = WorkflowGraph()

    async def node(state):
        state.results.append("ok")
        return state

    graph.register_node("demo", node)

    result = await graph.run(WorkflowState(task_id="1", current_agent="demo"))

    assert result.results == ["ok"]
    assert result.error is None


@pytest.mark.asyncio
async def test_workflow_exception_recovery():
    """验证节点异常会记录状态，不影响服务。"""
    graph = WorkflowGraph()

    async def failed_node(state):
        raise RuntimeError("node failed")

    graph.register_node("failed", failed_node)

    result = await graph.run(WorkflowState(task_id="1", current_agent="failed"))

    assert result.error == "node failed"

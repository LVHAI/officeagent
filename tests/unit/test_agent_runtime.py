import pytest

from officeagent.core.agent import SupervisorAgent
from officeagent.core.models import AgentContext


@pytest.mark.asyncio
async def test_supervisor_agent_execute():
    """验证 Supervisor Agent 基础执行流程。

    测试目标：
    - Agent 可以正常接收 Context；
    - execute 方法返回统一 AgentResult；
    - 成功结果包含任务 ID。
    """

    result = await SupervisorAgent().execute(
        AgentContext(task_id="test-task", payload={})
    )

    assert result.success is True
    assert result.data["task_id"] == "test-task"

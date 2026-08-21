import pytest

from officeagent.core.agent import SupervisorAgent
from officeagent.core.models import AgentContext


@pytest.mark.asyncio
async def test_supervisor_agent_execute():
    result = await SupervisorAgent().execute(
        AgentContext(task_id="test-task", payload={})
    )

    assert result.success is True
    assert result.data["task_id"] == "test-task"

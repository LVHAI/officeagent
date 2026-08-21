import pytest

from officeagent.core.agent import AgentResult, BaseAgent


class DemoAgent(BaseAgent):
    async def _execute(self, context):
        return AgentResult(success=True, data=context)


@pytest.mark.asyncio
async def test_agent_execute_success():
    result = await DemoAgent().execute({"task_id": "1"})
    assert result.success is True
    assert result.data["task_id"] == "1"


class BrokenAgent(BaseAgent):
    async def _execute(self, context):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_agent_exception_is_normalized():
    result = await BrokenAgent().execute({})
    assert result.success is False
    assert result.error_code == "INTERNAL_ERROR"

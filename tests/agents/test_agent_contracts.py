from app.agents.contracts import AgentInput, AgentOutput, Source


def test_agent_contracts_preserve_execution_context_and_sources():
    request = AgentInput(
        task_id="t1",
        parent_agent_id="supervisor",
        query="查询客户 C001",
        context={"customer_id": "C001"},
        constraints={"max_results": 10},
    )
    output = AgentOutput(
        agent_id="tool-agent",
        status="completed",
        result={"customer_id": "C001"},
        sources=[Source(kind="sql", title="CRM", metadata={"rows": 1})],
        elapsed_ms=12.5,
    )

    assert request.parent_agent_id == "supervisor"
    assert request.context["customer_id"] == "C001"
    assert output.sources[0].metadata["rows"] == 1

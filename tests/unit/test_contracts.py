from app.agents.contracts import AgentInput, AgentOutput, Source


def test_agent_contracts_are_serializable():
    source = Source(kind="knowledge", title="policy.pdf", metadata={"page": 12})
    output = AgentOutput(
        agent_id="knowledge-agent",
        status="completed",
        result={"answer": "ok"},
        sources=[source],
    )
    value = output.to_dict()
    assert value["agent_id"] == "knowledge-agent"
    assert value["sources"][0]["metadata"]["page"] == 12


def test_agent_input_keeps_parent_and_constraints_explicit():
    value = AgentInput(
        task_id="t1",
        query="query",
        parent_agent_id="supervisor",
        constraints={"timeout": 5},
    )
    assert value.parent_agent_id == "supervisor"
    assert value.constraints["timeout"] == 5

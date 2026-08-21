from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)


class AgentState(TypedDict, total=False):
    query: str
    plan: str
    knowledge: Any
    tool: Any
    web: Any
    report: Any
    errors: list[str]


async def _invoke(agent, query: str) -> Any:
    result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
    return result


async def supervisor_node(state: AgentState) -> dict:
    result = await _invoke(create_supervisor(), state["query"])
    messages = result.get("messages", []) if isinstance(result, dict) else []
    plan = messages[-1].content if messages else str(result)
    return {"plan": plan}


async def worker_node(state: AgentState) -> dict:
    query = state["query"]
    agents = {
        "knowledge": create_knowledge_agent(),
        "tool": create_tool_agent(),
        "web": create_web_agent(),
    }
    results = await asyncio.gather(
        *(_invoke(agent, query) for agent in agents.values()),
        return_exceptions=True,
    )
    output: dict[str, Any] = {}
    errors = list(state.get("errors", []))
    for name, result in zip(agents, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
        else:
            output[name] = result
    output["errors"] = errors
    return output


async def report_node(state: AgentState) -> dict:
    context = {
        "query": state["query"],
        "plan": state.get("plan"),
        "knowledge": state.get("knowledge"),
        "tool": state.get("tool"),
        "web": state.get("web"),
        "errors": state.get("errors", []),
    }
    result = await _invoke(create_report_agent(), str(context))
    return {"report": result}


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("workers", worker_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "workers")
    graph.add_edge("workers", "report")
    graph.add_edge("report", END)
    return graph.compile()

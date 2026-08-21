from __future__ import annotations

import asyncio
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)
from app.core.execution import run_with_timeout
from app.core.trace import AgentTrace


class AgentState(TypedDict, total=False):
    query: str
    plan: str
    knowledge: Any
    tool: Any
    web: Any
    report: Any
    errors: list[str]
    traces: list[dict[str, Any]]


AGENT_TIMEOUT_SECONDS = 45.0


async def _invoke(agent, query: str, agent_id: str, task_id: str) -> tuple[Any, dict[str, Any]]:
    trace = AgentTrace(task_id=task_id, agent_id=agent_id)
    try:
        result = await run_with_timeout(
            agent.ainvoke({"messages": [{"role": "user", "content": query}]}),
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        trace.finish()
        return result, trace.to_dict()
    except Exception as exc:
        trace.finish(status="failed", error=str(exc))
        raise


async def supervisor_node(state: AgentState) -> dict:
    task_id = str(uuid4())
    result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
    messages = result.get("messages", []) if isinstance(result, dict) else []
    plan = messages[-1].content if messages else str(result)
    return {"plan": plan, "traces": [trace]}


async def worker_node(state: AgentState) -> dict:
    task_id = str(uuid4())
    agents = {
        "knowledge": create_knowledge_agent(),
        "tool": create_tool_agent(),
        "web": create_web_agent(),
    }
    results = await asyncio.gather(
        *(_invoke(agent, state["query"], name, task_id) for name, agent in agents.items()),
        return_exceptions=True,
    )
    output: dict[str, Any] = {}
    errors = list(state.get("errors", []))
    traces = list(state.get("traces", []))
    for name, result in zip(agents, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
            traces.append(
                AgentTrace(task_id=task_id, agent_id=name, status="failed", error=str(result)).to_dict()
            )
        else:
            value, trace = result
            output[name] = value
            traces.append(trace)
    output["errors"] = errors
    output["traces"] = traces
    return output


async def report_node(state: AgentState) -> dict:
    task_id = str(uuid4())
    context = {
        "query": state["query"],
        "plan": state.get("plan"),
        "knowledge": state.get("knowledge"),
        "tool": state.get("tool"),
        "web": state.get("web"),
        "errors": state.get("errors", []),
    }
    result, trace = await _invoke(create_report_agent(), str(context), "report", task_id)
    return {"report": result, "traces": [trace]}


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

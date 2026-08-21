from __future__ import annotations

import asyncio
import operator
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.contracts import DelegationTrace
from app.agents.deepagents import create_report_agent, create_supervisor
from app.core.checkpoint import get_checkpointer
from app.core.config import settings
from app.core.execution import run_with_timeout
from app.core.trace import AgentTrace


class AgentState(TypedDict, total=False):
    query: str
    task_id: str
    supervisor_result: Any
    report: Any
    status: str
    errors: Annotated[list[str], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]
    delegations: Annotated[list[dict[str, Any]], operator.add]


AGENT_TIMEOUT_SECONDS = 45.0
GLOBAL_TIMEOUT_SECONDS = 120.0


async def _invoke(agent, query: str, agent_id: str, task_id: str, parent_agent_id: str | None = None):
    trace = AgentTrace(task_id=task_id, agent_id=agent_id, parent_agent_id=parent_agent_id)
    try:
        result = await run_with_timeout(
            agent.ainvoke({"messages": [{"role": "user", "content": query}]}),
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        trace.finish()
        return result, trace.to_dict()
    except asyncio.CancelledError:
        trace.finish(status="cancelled", error="agent task cancelled")
        raise
    except Exception as exc:
        trace.finish(status="failed", error=str(exc))
        raise


def _delegation(task_id: str, child: str, status: str, elapsed_ms: float = 0.0, error: str | None = None):
    return DelegationTrace(
        task_id=task_id,
        delegation_id=str(uuid4()),
        parent_agent_id="supervisor",
        child_agent_id=child,
        status=status,
        elapsed_ms=elapsed_ms,
        error=error,
    ).__dict__


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor DeepAgent 自主规划并通过 task/subagents 完成 Delegation。"""
    task_id = state["task_id"]
    started = asyncio.get_running_loop().time()
    try:
        result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        delegations = [
            _delegation(task_id, name, "completed", elapsed_ms=elapsed)
            for name in ("knowledge-agent", "tool-agent", "web-agent")
            if name.replace("-agent", "") in str(result).lower()
        ]
        return {"supervisor_result": result, "traces": [trace], "delegations": delegations}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {
            "status": "partial",
            "errors": [f"supervisor: {exc}"],
            "traces": [
                AgentTrace(task_id=task_id, agent_id="supervisor", status="failed", error=str(exc)).to_dict()
            ],
        }


async def report_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    context = {
        "query": state["query"],
        "supervisor_result": state.get("supervisor_result"),
        "errors": state.get("errors", []),
        "delegations": state.get("delegations", []),
    }
    try:
        result, trace = await _invoke(
            create_report_agent(), str(context), "report", task_id, parent_agent_id="supervisor"
        )
        return {"report": result, "status": "completed", "traces": [trace]}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {
            "status": "partial",
            "errors": [f"report: {exc}"],
            "traces": [
                AgentTrace(
                    task_id=task_id,
                    agent_id="report",
                    parent_agent_id="supervisor",
                    status="failed",
                    error=str(exc),
                ).to_dict()
            ],
        }


def build_workflow():
    """LangGraph 负责外层 State/Checkpoint；测试环境仍使用 InMemorySaver。"""
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "report")
    graph.add_edge("report", END)
    checkpointer = InMemorySaver() if settings.environment == "test" else get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


def new_task_state(query: str) -> AgentState:
    return {"query": query, "task_id": str(uuid4()), "errors": [], "traces": [], "delegations": []}

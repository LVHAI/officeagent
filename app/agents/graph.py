from __future__ import annotations

import asyncio
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import operator
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.deepagents import create_report_agent, create_supervisor
from app.core.execution import run_with_timeout
from app.core.trace import AgentTrace


class AgentState(TypedDict, total=False):
    query: str
    task_id: str
    supervisor_result: Any
    report: Any
    # 并行/多次 Delegation 的 Trace 与错误必须通过 reducer 合并，不能相互覆盖。
    errors: Annotated[list[str], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]


AGENT_TIMEOUT_SECONDS = 45.0


async def _invoke(agent, query: str, agent_id: str, task_id: str) -> tuple[Any, dict[str, Any]]:
    # 每个 Agent 沿用同一个 task_id，便于追踪 Supervisor → Sub-Agent 调用链。
    trace = AgentTrace(task_id=task_id, agent_id=agent_id)
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


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """运行 Supervisor DeepAgent；由其 task 工具自主决定委派哪些子 Agent。"""
    task_id = state["task_id"]
    result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
    return {"supervisor_result": result, "traces": [trace]}


async def report_node(state: AgentState) -> dict[str, Any]:
    """将 Supervisor 已经完成的 Delegation 结果交给轻量 Report Agent。"""
    task_id = state["task_id"]
    context = {
        "query": state["query"],
        "supervisor_result": state.get("supervisor_result"),
        "errors": state.get("errors", []),
    }
    try:
        result, trace = await _invoke(
            create_report_agent(), str(context), "report", task_id
        )
        return {"report": result, "traces": [trace]}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {
            "errors": [f"report: {exc}"],
            "traces": [
                AgentTrace(
                    task_id=task_id,
                    agent_id="report",
                    status="failed",
                    error=str(exc),
                ).to_dict()
            ],
        }


def build_workflow():
    # Supervisor 内部通过 DeepAgents task/subagents 做 Agentic Delegation；
    # LangGraph 只负责外层 Workflow、State、Checkpoint 和生命周期管理。
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=InMemorySaver())


def new_task_state(query: str) -> AgentState:
    """创建独立任务 State，避免不同请求之间共享 Agent 状态。"""
    return {"query": query, "task_id": str(uuid4()), "errors": [], "traces": []}

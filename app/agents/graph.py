from __future__ import annotations

import asyncio
import operator
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)
from app.core.execution import gather_bounded, run_with_timeout
from app.core.trace import AgentTrace


class AgentState(TypedDict, total=False):
    query: str
    task_id: str
    plan: str
    knowledge: Any
    tool: Any
    web: Any
    report: Any
    # LangGraph reducer 合并并行节点的 Trace / Error，避免后写覆盖先写。
    errors: Annotated[list[str], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]


AGENT_TIMEOUT_SECONDS = 45.0
MAX_WORKER_CONCURRENCY = 3
WORKER_GLOBAL_TIMEOUT_SECONDS = 90.0


async def _invoke(agent, query: str, agent_id: str, task_id: str) -> tuple[Any, dict[str, Any]]:
    # 每个 Agent 使用同一个 task_id，形成完整的任务级调用链。
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


async def supervisor_node(state: AgentState) -> dict:
    # Supervisor DeepAgent 负责规划和委派；LangGraph 负责外层状态流转。
    task_id = state["task_id"]
    result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
    messages = result.get("messages", []) if isinstance(result, dict) else []
    plan = messages[-1].content if messages else str(result)
    return {"plan": plan, "traces": [trace]}


async def _run_workers(state: AgentState, task_id: str) -> list[Any]:
    # 独立 Worker 并发执行，并通过 semaphore 控制最大并发度。
    agents = {
        "knowledge": create_knowledge_agent(),
        "tool": create_tool_agent(),
        "web": create_web_agent(),
    }
    operations = [
        _invoke(agent, f"Execution plan:\n{state.get('plan', '')}\n\nUser query:\n{state['query']}", name, task_id)
        for name, agent in agents.items()
    ]
    return await gather_bounded(operations, MAX_WORKER_CONCURRENCY)


async def worker_node(state: AgentState) -> dict:
    task_id = state["task_id"]
    agents = {"knowledge": None, "tool": None, "web": None}
    try:
        results = await run_with_timeout(
            _run_workers(state, task_id),
            timeout=WORKER_GLOBAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        # 全局超时后取消未完成 Worker，避免后台任务继续占用模型或 MCP 资源。
        return {
            "errors": ["workers: global timeout"],
            "traces": [
                AgentTrace(
                    task_id=task_id,
                    agent_id=name,
                    status="timeout",
                    error="worker global timeout",
                ).to_dict()
                for name in agents
            ],
        }

    output: dict[str, Any] = {}
    errors: list[str] = []
    traces: list[dict[str, Any]] = []
    for name, result in zip(agents, results):
        if isinstance(result, BaseException):
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
    # Report Agent 汇总 Worker 结果，并继续沿用同一个 task_id。
    task_id = state["task_id"]
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
    # InMemorySaver 用于本地开发的 Checkpoint；生产环境可替换为持久化 Checkpointer。
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("workers", worker_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "workers")
    graph.add_edge("workers", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=InMemorySaver())

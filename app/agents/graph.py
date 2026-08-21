from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict
from uuid import uuid4

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
    # 一个 HTTP 请求对应一个 task_id，所有 Agent Trace 共用它，方便完整审计。
    task_id: str
    plan: str
    knowledge: Any
    tool: Any
    web: Any
    report: Any
    # LangGraph 使用 reducer 合并不同节点产生的 Trace / Error，避免后一个节点覆盖前一个节点。
    errors: Annotated[list[str], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]


# 单个 Agent 的超时时间；避免某一个外部模型调用长期占用整个任务。
AGENT_TIMEOUT_SECONDS = 45.0
# 当前 MVP 限制并行 Agent 数量，避免模型和 MCP 服务瞬间被打满。
AGENT_CONCURRENCY_LIMIT = 3


async def _invoke(agent, query: str, agent_id: str, task_id: str) -> tuple[Any, dict[str, Any]]:
    # 每次 Agent 调用都建立独立 Trace，但复用整个 Workflow 的 task_id。
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
    # Supervisor 负责理解任务和规划，不直接承担所有业务查询。
    task_id = state.get("task_id") or str(uuid4())
    result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
    messages = result.get("messages", []) if isinstance(result, dict) else []
    plan = messages[-1].content if messages else str(result)
    return {"task_id": task_id, "plan": plan, "traces": [trace]}


async def worker_node(state: AgentState) -> dict:
    # 三类独立任务并发执行，降低多个 Agent 串行调用造成的整体延迟。
    task_id = state.get("task_id") or str(uuid4())
    agents = {
        "knowledge": create_knowledge_agent(),
        "tool": create_tool_agent(),
        "web": create_web_agent(),
    }
    results = await gather_bounded(
        [_invoke(agent, state["query"], name, task_id) for name, agent in agents.items()],
        limit=AGENT_CONCURRENCY_LIMIT,
    )
    output: dict[str, Any] = {"task_id": task_id}
    errors: list[str] = []
    traces: list[dict[str, Any]] = []
    for name, result in zip(agents, results):
        if isinstance(result, BaseException):
            # 单个 Agent 失败只记录 Partial Failure，不影响其他独立 Agent 的结果。
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
    # Report Agent 只负责汇总已经获取的数据，并保留失败信息和来源。
    task_id = state.get("task_id") or str(uuid4())
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
    # LangGraph 负责状态和流程控制；具体 Multi-Agent Runtime 由 DeepAgents 提供。
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("workers", worker_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "workers")
    graph.add_edge("workers", "report")
    graph.add_edge("report", END)
    return graph.compile()

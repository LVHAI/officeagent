from __future__ import annotations

import asyncio
import logging
import operator
import time
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.contracts import DelegationTrace
from app.agents.deepagents import create_report_agent, create_supervisor
from app.agents.mcp_registry import mcp_registry
from app.core.checkpoint import get_checkpointer
from app.core.config import settings
from app.core.execution import run_with_timeout
from app.core.trace import AgentTrace

logger = logging.getLogger(__name__)


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
AGENT_PROGRESS_LOG_INTERVAL_SECONDS = 5.0


async def _log_agent_progress(task: asyncio.Task, task_id: str, agent_id: str, started: float) -> None:
    """Emit periodic progress so a long LLM/tool call is observable instead of looking hung."""
    try:
        while not task.done():
            await asyncio.sleep(AGENT_PROGRESS_LOG_INTERVAL_SECONDS)
            if not task.done():
                logger.info(
                    "agent.invoke.progress task_id=%s agent=%s elapsed_ms=%.1f",
                    task_id,
                    agent_id,
                    (time.perf_counter() - started) * 1000,
                )
    except asyncio.CancelledError:
        raise


async def _invoke(agent, query: str, agent_id: str, task_id: str, parent_agent_id: str | None = None):
    trace = AgentTrace(task_id=task_id, agent_id=agent_id, parent_agent_id=parent_agent_id)
    started = time.perf_counter()
    logger.info(
        "agent.invoke.start task_id=%s agent=%s parent=%s input_length=%d agent_type=%s",
        task_id,
        agent_id,
        parent_agent_id or "-",
        len(query),
        type(agent).__name__,
    )
    operation = asyncio.create_task(
        agent.ainvoke({
            "messages": [{"role": "user", "content": query}],
            "task_id": task_id,
        })
    )
    progress_task = asyncio.create_task(_log_agent_progress(operation, task_id, agent_id, started))
    try:
        result = await run_with_timeout(operation, timeout=AGENT_TIMEOUT_SECONDS)
        trace.finish()
        logger.info(
            "agent.invoke.completed task_id=%s agent=%s elapsed_ms=%.1f result_type=%s",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
            type(result).__name__,
        )
        return result, trace.to_dict()
    except asyncio.TimeoutError:
        trace.finish(status="failed", error=f"agent timeout after {AGENT_TIMEOUT_SECONDS:.1f}s")
        logger.error(
            "agent.invoke.timeout task_id=%s agent=%s timeout_seconds=%.1f elapsed_ms=%.1f",
            task_id,
            agent_id,
            AGENT_TIMEOUT_SECONDS,
            (time.perf_counter() - started) * 1000,
        )
        raise
    except asyncio.CancelledError:
        trace.finish(status="cancelled", error="agent task cancelled")
        logger.warning("agent.invoke.cancelled task_id=%s agent=%s", task_id, agent_id)
        raise
    except Exception as exc:
        trace.finish(status="failed", error=str(exc))
        logger.exception(
            "agent.invoke.failed task_id=%s agent=%s elapsed_ms=%.1f error_type=%s",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
            type(exc).__name__,
        )
        raise
    finally:
        progress_task.cancel()
        await asyncio.gather(progress_task, return_exceptions=True)


def _delegation(
    task_id: str,
    child: str,
    status: str,
    *,
    reason: str = "",
    elapsed_ms: float = 0.0,
    error: str | None = None,
):
    return DelegationTrace(
        task_id=task_id,
        delegation_id=str(uuid4()),
        parent_agent_id="supervisor",
        child_agent_id=child,
        status=status,
        reason=reason,
        elapsed_ms=elapsed_ms,
        error=error,
    ).__dict__


def _supervisor_tools() -> dict[str, list[Any]]:
    """Expose only deterministic knowledge tools to the Supervisor runtime.

    Enterprise MCP tools belong behind Tool Agent -> Skill Runtime -> MCP. They must
    not be registered directly on the Supervisor, otherwise the context grows with
    the enterprise tool catalog and bypasses the Skill boundary.
    """
    return {"knowledge": mcp_registry.tools("knowledge")}


def _message_value(message: Any, key: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def _extract_delegations(result: Any, task_id: str) -> list[dict[str, Any]]:
    """Build delegation traces only from actual DeepAgents `task` tool calls.

    The previous implementation searched the Supervisor's final natural-language
    response for agent names. That could report a delegation even when no subagent
    was called. DeepAgents exposes subagent execution through the `task` tool, so the
    trace must be derived from those tool-call records instead.

    The event is deliberately marked `delegated`, not `completed`: the current graph
    boundary observes the Supervisor's tool-call history but does not yet receive a
    child-agent lifecycle callback with an accurate duration. A future execution
    event stream can upgrade this to completed/failed without changing the contract.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
    delegations: list[dict[str, Any]] = []
    for message in messages or []:
        tool_calls = _message_value(message, "tool_calls", []) or []
        for call in tool_calls:
            if not isinstance(call, dict) or call.get("name") != "task":
                continue
            args = call.get("args") or {}
            child = args.get("subagent_type")
            if not child:
                continue
            reason = str(args.get("description", "")).strip()
            delegations.append(
                _delegation(
                    task_id,
                    child,
                    "delegated",
                    reason=reason,
                )
            )
    return delegations


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    started = asyncio.get_running_loop().time()
    logger.info("workflow.supervisor.start task_id=%s query_length=%d", task_id, len(state["query"]))
    try:
        tools = _supervisor_tools()
        logger.info(
            "workflow.supervisor.tools task_id=%s knowledge=%d enterprise=skill_runtime",
            task_id,
            len(tools["knowledge"]),
        )
        result, trace = await _invoke(
            create_supervisor(knowledge_tools=tools["knowledge"]),
            state["query"],
            "supervisor",
            task_id,
        )
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        delegations = _extract_delegations(result, task_id)
        logger.info(
            "workflow.supervisor.completed task_id=%s elapsed_ms=%.1f delegations=%d",
            task_id,
            elapsed,
            len(delegations),
        )
        return {"supervisor_result": result, "traces": [trace], "delegations": delegations}
    except asyncio.CancelledError:
        logger.warning("workflow.supervisor.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception("workflow.supervisor.failed task_id=%s elapsed_ms=%.1f", task_id, (asyncio.get_running_loop().time() - started) * 1000)
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
    started = time.perf_counter()
    logger.info(
        "workflow.report.start task_id=%s context_length=%d supervisor_result_type=%s errors=%d",
        task_id,
        len(str(context)),
        type(state.get("supervisor_result")).__name__,
        len(state.get("errors", [])),
    )
    try:
        result, trace = await _invoke(
            create_report_agent(), str(context), "report", task_id, parent_agent_id="supervisor"
        )
        logger.info("workflow.report.completed task_id=%s elapsed_ms=%.1f", task_id, (time.perf_counter() - started) * 1000)
        return {"report": result, "status": "completed", "traces": [trace]}
    except asyncio.CancelledError:
        logger.warning("workflow.report.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception("workflow.report.failed task_id=%s elapsed_ms=%.1f error_type=%s", task_id, (time.perf_counter() - started) * 1000, type(exc).__name__)
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
    logger.info("workflow.build.start environment=%s", settings.environment)
    started = time.perf_counter()
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "report")
    graph.add_edge("report", END)
    checkpointer = InMemorySaver() if settings.environment == "test" else get_checkpointer()
    workflow = graph.compile(checkpointer=checkpointer)
    logger.info("workflow.build.completed elapsed_ms=%.1f checkpointer=%s", (time.perf_counter() - started) * 1000, type(checkpointer).__name__)
    return workflow


def new_task_state(query: str) -> AgentState:
    return {"query": query, "task_id": str(uuid4()), "errors": [], "traces": [], "delegations": []}

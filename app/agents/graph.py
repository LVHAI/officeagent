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
    try:
        while not task.done():
            await asyncio.sleep(AGENT_PROGRESS_LOG_INTERVAL_SECONDS)
            if not task.done():
                logger.info(
                    "agent.invoke.progress task_id=%s agent=%s elapsed_ms=%.1f",
                    task_id, agent_id, (time.perf_counter() - started) * 1000,
                )
    except asyncio.CancelledError:
        raise


async def _invoke(agent, query: str, agent_id: str, task_id: str, parent_agent_id: str | None = None):
    trace = AgentTrace(task_id=task_id, agent_id=agent_id, parent_agent_id=parent_agent_id)
    started = time.perf_counter()
    logger.info(
        "agent.invoke.start task_id=%s agent=%s parent=%s input_length=%d agent_type=%s",
        task_id, agent_id, parent_agent_id or "-", len(query), type(agent).__name__,
    )
    operation = asyncio.create_task(agent.ainvoke({"messages": [{"role": "user", "content": query}], "task_id": task_id}))
    progress_task = asyncio.create_task(_log_agent_progress(operation, task_id, agent_id, started))
    try:
        result = await run_with_timeout(operation, timeout=AGENT_TIMEOUT_SECONDS)
        trace.finish()
        logger.info("agent.invoke.completed task_id=%s agent=%s elapsed_ms=%.1f result_type=%s", task_id, agent_id, (time.perf_counter() - started) * 1000, type(result).__name__)
        return result, trace.to_dict()
    except asyncio.TimeoutError:
        trace.finish(status="failed", error=f"agent timeout after {AGENT_TIMEOUT_SECONDS:.1f}s")
        logger.error("agent.invoke.timeout task_id=%s agent=%s timeout_seconds=%.1f elapsed_ms=%.1f", task_id, agent_id, AGENT_TIMEOUT_SECONDS, (time.perf_counter() - started) * 1000)
        raise
    except asyncio.CancelledError:
        trace.finish(status="cancelled", error="agent task cancelled")
        logger.warning("agent.invoke.cancelled task_id=%s agent=%s", task_id, agent_id)
        raise
    except Exception as exc:
        trace.finish(status="failed", error=str(exc))
        logger.exception("agent.invoke.failed task_id=%s agent=%s elapsed_ms=%.1f error_type=%s", task_id, agent_id, (time.perf_counter() - started) * 1000, type(exc).__name__)
        raise
    finally:
        progress_task.cancel()
        await asyncio.gather(progress_task, return_exceptions=True)


def _delegation(task_id: str, child: str, status: str, *, reason: str = "", elapsed_ms: float = 0.0, error: str | None = None, delegation_id: str | None = None):
    return DelegationTrace(
        task_id=task_id,
        delegation_id=delegation_id or str(uuid4()),
        parent_agent_id="supervisor",
        child_agent_id=child,
        status=status,
        reason=reason,
        elapsed_ms=elapsed_ms,
        error=error,
    ).__dict__


def _message_value(message: Any, key: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def _tool_call_args(call: Any) -> dict[str, Any]:
    args = call.get("args") if isinstance(call, dict) else getattr(call, "args", None)
    return args if isinstance(args, dict) else {}


def _extract_delegations(result: Any, task_id: str) -> list[dict[str, Any]]:
    """Trace both task delegation calls and their corresponding tool results."""
    messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
    delegations: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    for message in messages or []:
        message_type = type(message).__name__
        tool_calls = _message_value(message, "tool_calls", []) or []
        if tool_calls:
            for call in tool_calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if name != "task":
                    continue
                call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
                args = _tool_call_args(call)
                child = str(args.get("subagent_type") or "").strip()
                if not child:
                    continue
                reason = str(args.get("description", "")).strip()
                entry = _delegation(task_id, child, "running", reason=reason, delegation_id=str(call_id or uuid4()))
                pending[str(call_id)] = entry
                delegations.append(entry)
                logger.info("delegation.start task_id=%s delegation_id=%s child=%s reason=%s", task_id, entry["delegation_id"], child, reason)

        if message_type == "ToolMessage" or _message_value(message, "type") == "tool":
            tool_call_id = _message_value(message, "tool_call_id") or _message_value(message, "id")
            if tool_call_id is not None and str(tool_call_id) in pending:
                entry = pending[str(tool_call_id)]
                raw_content = _message_value(message, "content", "")
                content = str(raw_content)
                is_error = bool(_message_value(message, "is_error", False)) or content.lower().startswith(("error", "exception"))
                entry["status"] = "failed" if is_error else "completed"
                entry["elapsed_ms"] = 0.0
                if is_error:
                    entry["error"] = content[:2000]
                logger.info("delegation.%s task_id=%s delegation_id=%s child=%s result_length=%d", "failed" if is_error else "completed", task_id, entry["delegation_id"], entry["child_agent_id"], len(content))

    for entry in delegations:
        if entry["status"] == "running":
            entry["status"] = "completed"
            logger.info("delegation.result_unobserved task_id=%s delegation_id=%s child=%s action=mark_completed_without_tool_message", task_id, entry["delegation_id"], entry["child_agent_id"])

    logger.info("delegation.summary task_id=%s total=%d statuses=%s", task_id, len(delegations), [entry["status"] for entry in delegations])
    return delegations


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    started = asyncio.get_running_loop().time()
    logger.info("workflow.supervisor.start task_id=%s query_length=%d", task_id, len(state["query"]))
    try:
        result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        delegations = _extract_delegations(result, task_id)
        logger.info("workflow.supervisor.completed task_id=%s elapsed_ms=%.1f delegations=%d", task_id, elapsed, len(delegations))
        return {"supervisor_result": result, "traces": [trace], "delegations": delegations}
    except asyncio.CancelledError:
        logger.warning("workflow.supervisor.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception("workflow.supervisor.failed task_id=%s elapsed_ms=%.1f", task_id, (asyncio.get_running_loop().time() - started) * 1000)
        return {"status": "partial", "errors": [f"supervisor: {exc}"], "traces": [AgentTrace(task_id=task_id, agent_id="supervisor", status="failed", error=str(exc)).to_dict()]}


async def report_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    context = {"query": state["query"], "supervisor_result": state.get("supervisor_result"), "errors": state.get("errors", []), "delegations": state.get("delegations", [])}
    started = time.perf_counter()
    logger.info("workflow.report.start task_id=%s context_length=%d supervisor_result_type=%s errors=%d", task_id, len(str(context)), type(state.get("supervisor_result")).__name__, len(state.get("errors", [])))
    try:
        result, trace = await _invoke(create_report_agent(), str(context), "report", task_id, parent_agent_id="supervisor")
        logger.info("workflow.report.completed task_id=%s elapsed_ms=%.1f", task_id, (time.perf_counter() - started) * 1000)
        return {"report": result, "status": "completed", "traces": [trace]}
    except asyncio.CancelledError:
        logger.warning("workflow.report.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception("workflow.report.failed task_id=%s elapsed_ms=%.1f error_type=%s", task_id, (time.perf_counter() - started) * 1000, type(exc).__name__, exc)
        return {"status": "partial", "errors": [f"report: {exc}"], "traces": [AgentTrace(task_id=task_id, agent_id="report", parent_agent_id="supervisor", status="failed", error=str(exc)).to_dict()]}


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

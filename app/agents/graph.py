from __future__ import annotations

import asyncio
import logging
import operator
import time
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.contracts import AgentOutput, DelegationTrace
from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_supervisor,
    create_tool_agent,
    create_web_agent,
)
from app.core.checkpoint import get_checkpointer
from app.core.config import settings
from app.core.execution import retry_async, run_with_timeout
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
    agent_outputs: Annotated[list[dict[str, Any]], operator.add]


AGENT_TIMEOUT_SECONDS = 45.0
GLOBAL_TIMEOUT_SECONDS = 120.0
AGENT_PROGRESS_LOG_INTERVAL_SECONDS = 5.0
REDELEGATION_LIMIT = 1


async def _log_agent_progress(task: asyncio.Task, task_id: str, agent_id: str, started: float) -> None:
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

    async def invoke_once():
        attempt_started = time.perf_counter()
        logger.info(
            "agent.invoke.start task_id=%s agent=%s parent=%s input_length=%d agent_type=%s",
            task_id,
            agent_id,
            parent_agent_id or "-",
            len(query),
            type(agent).__name__,
        )
        operation = asyncio.create_task(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": query}], "task_id": task_id}
            )
        )
        progress_task = asyncio.create_task(
            _log_agent_progress(operation, task_id, agent_id, attempt_started)
        )
        try:
            return await run_with_timeout(operation, timeout=AGENT_TIMEOUT_SECONDS)
        finally:
            if not operation.done():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)

    try:
        result = await retry_async(
            invoke_once,
            retries=1,
            base_delay=0.25,
            retryable=lambda exc: isinstance(exc, (TimeoutError, ConnectionError)),
        )
        trace.finish()
        logger.info(
            "agent.invoke.completed task_id=%s agent=%s elapsed_ms=%.1f result_type=%s",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
            type(result).__name__,
        )
        return result, trace.to_dict()
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


def _delegation(
    task_id: str,
    child: str,
    status: str,
    *,
    reason: str = "",
    elapsed_ms: float = 0.0,
    error: str | None = None,
    delegation_id: str | None = None,
):
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
    """Trace task calls and preserve the distinction between delegated and completed."""
    messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
    delegations: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    for message in messages or []:
        message_type = type(message).__name__
        tool_calls = _message_value(message, "tool_calls", []) or []
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
            entry = _delegation(
                task_id,
                child,
                "delegated",
                reason=reason,
                delegation_id=str(call_id or uuid4()),
            )
            pending[str(call_id)] = entry
            delegations.append(entry)
            logger.info(
                "delegation.start task_id=%s delegation_id=%s child=%s reason=%s",
                task_id,
                entry["delegation_id"],
                child,
                reason,
            )

        if message_type == "ToolMessage" or _message_value(message, "type") == "tool":
            tool_call_id = _message_value(message, "tool_call_id") or _message_value(message, "id")
            if tool_call_id is None or str(tool_call_id) not in pending:
                continue
            entry = pending[str(tool_call_id)]
            raw_content = _message_value(message, "content", "")
            content = str(raw_content)
            is_error = bool(_message_value(message, "is_error", False)) or content.lower().startswith(
                ("error", "exception")
            )
            entry["status"] = "failed" if is_error else "completed"
            if is_error:
                entry["error"] = content[:2000]
            logger.info(
                "delegation.%s task_id=%s delegation_id=%s child=%s result_length=%d",
                "failed" if is_error else "completed",
                task_id,
                entry["delegation_id"],
                entry["child_agent_id"],
                len(content),
            )

    logger.info(
        "delegation.summary task_id=%s total=%d statuses=%s",
        task_id,
        len(delegations),
        [entry["status"] for entry in delegations],
    )
    return delegations


def _agent_output(
    task_id: str,
    agent_id: str,
    result: Any,
    trace: dict[str, Any],
    *,
    status: str = "completed",
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return AgentOutput(
        agent_id=agent_id,
        status=status,
        result=result,
        errors=errors or [],
        traces=[trace],
        elapsed_ms=float(trace.get("elapsed_ms", 0.0)),
    ).__dict__


async def _redelegate_failed(
    task_id: str,
    query: str,
    delegations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    failed = [entry for entry in delegations if entry["status"] == "failed"]
    if not failed:
        return [], [], []

    retry_entries: list[dict[str, Any]] = []
    retry_outputs: list[dict[str, Any]] = []
    retry_traces: list[dict[str, Any]] = []
    factories = {
        "knowledge-agent": create_knowledge_agent,
        "tool-agent": create_tool_agent,
        "web-agent": create_web_agent,
    }

    for entry in failed[:REDELEGATION_LIMIT]:
        child = entry["child_agent_id"]
        factory = factories.get(child)
        if factory is None:
            continue
        reason = entry.get("reason") or query
        retry_id = f"retry-{entry['delegation_id']}"
        logger.warning(
            "delegation.retry.start task_id=%s delegation_id=%s retry_id=%s child=%s",
            task_id,
            entry["delegation_id"],
            retry_id,
            child,
        )
        try:
            result, trace = await _invoke(
                factory(),
                reason,
                child,
                task_id,
                parent_agent_id="supervisor",
            )
            retry_entries.append(
                _delegation(
                    task_id,
                    child,
                    "completed",
                    reason=reason,
                    delegation_id=retry_id,
                )
            )
            retry_outputs.append(_agent_output(task_id, child, result, trace))
            retry_traces.append(trace)
            logger.info(
                "delegation.retry.completed task_id=%s retry_id=%s child=%s",
                task_id,
                retry_id,
                child,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            retry_entries.append(
                _delegation(
                    task_id,
                    child,
                    "failed",
                    reason=reason,
                    error=str(exc),
                    delegation_id=retry_id,
                )
            )
            retry_outputs.append(
                _agent_output(
                    task_id,
                    child,
                    None,
                    {"agent_id": child, "status": "failed", "error": str(exc)},
                    status="failed",
                    errors=[str(exc)],
                )
            )
            logger.exception(
                "delegation.retry.failed task_id=%s retry_id=%s child=%s",
                task_id,
                retry_id,
                child,
            )

    return retry_entries, retry_outputs, retry_traces


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    started = asyncio.get_running_loop().time()
    logger.info("workflow.supervisor.start task_id=%s query_length=%d", task_id, len(state["query"]))
    try:
        result, trace = await _invoke(create_supervisor(), state["query"], "supervisor", task_id)
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        delegations = _extract_delegations(result, task_id)
        retry_entries, retry_outputs, retry_traces = await _redelegate_failed(
            task_id,
            state["query"],
            delegations,
        )
        agent_outputs = [_agent_output(task_id, "supervisor", result, trace)] + retry_outputs
        logger.info(
            "workflow.supervisor.completed task_id=%s elapsed_ms=%.1f delegations=%d retries=%d",
            task_id,
            elapsed,
            len(delegations),
            len(retry_entries),
        )
        return {
            "supervisor_result": result,
            "traces": [trace, *retry_traces],
            "delegations": [*delegations, *retry_entries],
            "agent_outputs": agent_outputs,
        }
    except asyncio.CancelledError:
        logger.warning("workflow.supervisor.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception(
            "workflow.supervisor.failed task_id=%s elapsed_ms=%.1f",
            task_id,
            (asyncio.get_running_loop().time() - started) * 1000,
        )
        error_output = _agent_output(
            task_id,
            "supervisor",
            None,
            {"agent_id": "supervisor", "status": "failed", "error": str(exc)},
            status="failed",
            errors=[str(exc)],
        )
        return {
            "status": "partial",
            "errors": [f"supervisor: {exc}"],
            "traces": [{"agent_id": "supervisor", "status": "failed", "error": str(exc)}],
            "agent_outputs": [error_output],
        }


async def report_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    context = {
        "query": state["query"],
        "supervisor_result": state.get("supervisor_result"),
        "agent_outputs": state.get("agent_outputs", []),
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
            create_report_agent(),
            str(context),
            "report",
            task_id,
            parent_agent_id="supervisor",
        )
        logger.info(
            "workflow.report.completed task_id=%s elapsed_ms=%.1f",
            task_id,
            (time.perf_counter() - started) * 1000,
        )
        return {
            "report": result,
            "status": "completed",
            "traces": [trace],
            "agent_outputs": [_agent_output(task_id, "report", result, trace)],
        }
    except asyncio.CancelledError:
        logger.warning("workflow.report.cancelled task_id=%s", task_id)
        raise
    except Exception as exc:
        logger.exception(
            "workflow.report.failed task_id=%s elapsed_ms=%.1f error_type=%s",
            task_id,
            (time.perf_counter() - started) * 1000,
            type(exc).__name__,
        )
        error_output = _agent_output(
            task_id,
            "report",
            None,
            {"agent_id": "report", "status": "failed", "error": str(exc)},
            status="failed",
            errors=[str(exc)],
        )
        return {
            "status": "partial",
            "errors": [f"report: {exc}"],
            "traces": [{"agent_id": "report", "status": "failed", "error": str(exc)}],
            "agent_outputs": [error_output],
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
    logger.info(
        "workflow.build.completed elapsed_ms=%.1f checkpointer=%s",
        (time.perf_counter() - started) * 1000,
        type(checkpointer).__name__,
    )
    return workflow


def new_task_state(query: str) -> AgentState:
    return {
        "query": query,
        "task_id": str(uuid4()),
        "errors": [],
        "traces": [],
        "delegations": [],
        "agent_outputs": [],
    }

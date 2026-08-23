from __future__ import annotations

import asyncio
import logging
import operator
import time
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.aggregator import aggregate_agent_outputs
from app.agents.contracts import AgentOutput, DelegationTrace, Source
from app.agents.deepagents import (
    create_knowledge_agent,
    create_report_agent,
    create_tool_agent,
    create_web_agent,
)
from app.agents.execution_plan import ExecutionPlan, ExecutionTask
from app.agents.planner import (
    create_execution_planner,
    extract_execution_plan,
    validate_agent_selection,
)
from app.agents.scheduler import execute_with_dependencies
from app.core.checkpoint import get_checkpointer
from app.core.config import settings
from app.core.execution import retry_async, run_with_timeout
from app.core.trace import AgentTrace

logger = logging.getLogger(__name__)

AGENT_TIMEOUT_SECONDS = 45.0
GLOBAL_TIMEOUT_SECONDS = 120.0
AGENT_PROGRESS_LOG_INTERVAL_SECONDS = 5.0
MAX_PARALLEL_AGENTS = 3
MAX_REPLAN_ROUNDS = 1


class AgentState(TypedDict, total=False):
    query: str
    task_id: str
    execution_plan: dict[str, Any]
    supervisor_result: Any
    aggregated_context: dict[str, Any]
    report: Any
    status: str
    replan_count: int
    errors: Annotated[list[str], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]
    delegations: Annotated[list[dict[str, Any]], operator.add]
    agent_outputs: Annotated[list[dict[str, Any]], operator.add]


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


async def _invoke(agent: Any, query: str, agent_id: str, task_id: str, parent_agent_id: str | None = None):
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
            agent.ainvoke({"messages": [{"role": "user", "content": query}], "task_id": task_id})
        )
        progress_task = asyncio.create_task(_log_agent_progress(operation, task_id, agent_id, attempt_started))
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


def _delegation(task_id: str, task: ExecutionTask, status: str, *, elapsed_ms: float = 0.0, error: str | None = None):
    return DelegationTrace(
        task_id=task_id,
        delegation_id=task.task_id,
        parent_agent_id="supervisor",
        child_agent_id=task.agent,
        status=status,
        reason=task.query,
        elapsed_ms=elapsed_ms,
        error=error,
    ).__dict__


def _sources_from_result(result: Any) -> list[Source]:
    raw_sources = result.get("sources", []) if isinstance(result, dict) else getattr(result, "sources", [])
    sources: list[Source] = []
    for raw in raw_sources or []:
        if isinstance(raw, Source):
            sources.append(raw)
        elif isinstance(raw, dict):
            sources.append(
                Source(
                    kind=str(raw.get("kind", "unknown")),
                    title=str(raw.get("title", "")),
                    uri=str(raw.get("uri", "")),
                    metadata=dict(raw.get("metadata", {})),
                )
            )
    return sources


def _agent_output(agent_id: str, result: Any, trace: dict[str, Any], *, status: str = "completed", errors: list[str] | None = None) -> dict[str, Any]:
    return AgentOutput(
        agent_id=agent_id,
        status=status,
        result=result,
        sources=_sources_from_result(result),
        errors=errors or [],
        traces=[trace],
        elapsed_ms=float(trace.get("elapsed_ms", 0.0)),
    ).to_dict()


def _runtime_for(agent: str):
    return {
        "knowledge-agent": create_knowledge_agent,
        "tool-agent": create_tool_agent,
        "web-agent": create_web_agent,
    }[agent]


async def _execute_task(task: ExecutionTask, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    logger.info(
        "workflow.task.start task_id=%s execution_task_id=%s agent=%s parallel_group=%s depends_on=%s",
        task_id, task.task_id, task.agent, task.parallel_group, task.depends_on,
    )
    try:
        result, trace = await _invoke(
            _runtime_for(task.agent)(), task.query, task.agent, task_id, parent_agent_id="supervisor"
        )
        output = _agent_output(task.agent, result, trace)
        delegation = _delegation(task_id, task, "completed", elapsed_ms=(time.perf_counter() - started) * 1000)
        logger.info(
            "workflow.task.completed task_id=%s execution_task_id=%s agent=%s elapsed_ms=%.1f",
            task_id, task.task_id, task.agent, (time.perf_counter() - started) * 1000,
        )
        return output, delegation
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        output = _agent_output(
            task.agent,
            None,
            {"agent_id": task.agent, "status": "failed", "error": str(exc)},
            status="failed",
            errors=[str(exc)],
        )
        delegation = _delegation(
            task_id, task, "failed", elapsed_ms=(time.perf_counter() - started) * 1000, error=str(exc)
        )
        logger.exception(
            "workflow.task.failed task_id=%s execution_task_id=%s agent=%s error_type=%s",
            task_id, task.task_id, task.agent, type(exc).__name__,
        )
        return output, delegation


def _plan_query(query: str, prior_context: dict[str, Any] | None = None) -> str:
    if not prior_context:
        return query
    return (
        f"Original user request:\n{query}\n\n"
        "Previous execution results are below. Create a plan ONLY for missing or failed evidence; "
        "do not repeat successful work unless it is required to satisfy a dependency.\n"
        f"{prior_context}"
    )


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    started = time.perf_counter()
    logger.info("workflow.supervisor.plan.start task_id=%s query_length=%d", task_id, len(state["query"]))
    try:
        result, trace = await _invoke(
            create_execution_planner(),
            _plan_query(state["query"], state.get("aggregated_context")),
            "supervisor",
            task_id,
        )
        plan = extract_execution_plan(result)
        plan = validate_agent_selection(state["query"], plan)
        logger.info(
            "workflow.supervisor.plan.completed task_id=%s tasks=%d elapsed_ms=%.1f",
            task_id, len(plan.tasks), (time.perf_counter() - started) * 1000,
        )
        return {
            "execution_plan": plan.model_dump(),
            "supervisor_result": result,
            "traces": [trace],
            "delegations": [_delegation(task_id, task, "planned") for task in plan.tasks],
            "replan_count": state.get("replan_count", 0),
            "status": "planned",
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "workflow.supervisor.plan.failed task_id=%s error_type=%s",
            task_id, type(exc).__name__,
        )
        return {
            "status": "partial",
            "errors": [f"supervisor planning: {exc}"],
            "traces": [{"agent_id": "supervisor", "status": "failed", "error": str(exc)}],
            "replan_count": state.get("replan_count", 0),
        }


def _has_execution_plan(state: AgentState) -> bool:
    value = state.get("execution_plan")
    if not isinstance(value, dict) or not value.get("tasks"):
        logger.warning(
            "workflow.execution_plan.missing task_id=%s status=%s",
            state.get("task_id", "-"), state.get("status", "unknown"),
        )
        return False
    try:
        ExecutionPlan.model_validate(value)
    except Exception as exc:
        logger.warning(
            "workflow.execution_plan.invalid task_id=%s error_type=%s",
            state.get("task_id", "-"), type(exc).__name__,
        )
        return False
    return True


def _route_after_supervisor(state: AgentState) -> str:
    return "execute_plan" if _has_execution_plan(state) else "report"


async def execute_plan_node(state: AgentState) -> dict[str, Any]:
    plan = ExecutionPlan.model_validate(state["execution_plan"])
    task_id = state["task_id"]
    logger.info(
        "workflow.parallel.start task_id=%s tasks=%d max_parallel=%d",
        task_id, len(plan.tasks), MAX_PARALLEL_AGENTS,
    )
    results = await execute_with_dependencies(
        plan.tasks,
        lambda task: _execute_task(task, task_id),
        max_parallel=MAX_PARALLEL_AGENTS,
    )
    outputs = [item[0] for item in results]
    delegations = [item[1] for item in results]
    traces = [trace for output in outputs for trace in output.get("traces", [])]
    errors = [error for output in outputs for error in output.get("errors", [])]
    logger.info(
        "workflow.parallel.completed task_id=%s completed=%d failed=%d",
        task_id,
        sum(output["status"] == "completed" for output in outputs),
        sum(output["status"] != "completed" for output in outputs),
    )
    return {
        "agent_outputs": outputs,
        "delegations": delegations,
        "traces": traces,
        "errors": errors,
        "status": "partial" if errors else "executed",
    }


async def aggregate_node(state: AgentState) -> dict[str, Any]:
    context = aggregate_agent_outputs(state.get("agent_outputs", []))
    logger.info(
        "workflow.aggregate.completed task_id=%s successful=%d partial=%d failed=%d sources=%d",
        state["task_id"], len(context["successful_results"]), len(context["partial_results"]),
        len(context["failed_results"]), len(context["sources"]),
    )
    return {"aggregated_context": context}


def _needs_replan(state: AgentState) -> str:
    context = state.get("aggregated_context", {})
    if bool(context.get("failed_results")) and int(state.get("replan_count", 0)) < MAX_REPLAN_ROUNDS:
        return "replan"
    return "report"


async def replan_node(state: AgentState) -> dict[str, Any]:
    next_count = int(state.get("replan_count", 0)) + 1
    logger.info("workflow.supervisor.replan.start task_id=%s round=%d", state["task_id"], next_count)
    result = await supervisor_node({**state, "replan_count": next_count})
    result["replan_count"] = next_count
    logger.info("workflow.supervisor.replan.completed task_id=%s round=%d", state["task_id"], next_count)
    return result


def _route_after_replan(state: AgentState) -> str:
    return "execute_plan" if _has_execution_plan(state) else "report"


async def report_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    context = {
        "query": state["query"],
        "execution_plan": state.get("execution_plan"),
        "aggregated_context": state.get("aggregated_context", {}),
        "errors": state.get("errors", []),
        "delegations": state.get("delegations", []),
    }
    started = time.perf_counter()
    logger.info("workflow.report.start task_id=%s context_length=%d", task_id, len(str(context)))
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
            task_id, (time.perf_counter() - started) * 1000,
        )
        return {"report": result, "traces": [trace], "status": "completed"}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "workflow.report.failed task_id=%s error_type=%s",
            task_id, type(exc).__name__,
        )
        return {
            "status": "partial",
            "errors": [f"report: {exc}"],
            "traces": [{"agent_id": "report", "status": "failed", "error": str(exc)}],
        }

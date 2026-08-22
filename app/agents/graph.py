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
    logger.info("agent.invoke.start task_id=%s agent=%s parent=%s", task_id, agent_id, parent_agent_id or "-")
    operation = asyncio.create_task(
        agent.ainvoke({"messages": [{"role": "user", "content": query}]})
    )
    progress_task = asyncio.create_task(_log_agent_progress(operation, task_id, agent_id, started))
    try:
        result = await run_with_timeout(operation, timeout=AGENT_TIMEOUT_SECONDS)
        trace.finish()
        logger.info(
            "agent.invoke.completed task_id=%s agent=%s elapsed_ms=%.1f",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
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
        logger.exception("agent.invoke.failed task_id=%s agent=%s elapsed_ms=%.1f", task_id, agent_id, (time.perf_counter() - started) * 1000)
        raise
    finally:
        progress_task.cancel()
        await asyncio.gather(progress_task, return_exceptions=True)


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


def _supervisor_tools() -> dict[str, list[Any]]:
    return {
        "knowledge": mcp_registry.tools("knowledge"),
        "tool": mcp_registry.tools("crm", "database", "report"),
    }


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    task_id = state["task_id"]
    started = asyncio.get_running_loop().time()
    logger.info("workflow.supervisor.start task_id=%s", task_id)
    try:
        tools = _supervisor_tools()
        logger.info(
            "workflow.supervisor.tools task_id=%s knowledge=%d enterprise=%d",
            task_id,
            len(tools["knowledge"]),
            len(tools["tool"]),
        )
        result, trace = await _invoke(
            create_supervisor(
                knowledge_tools=tools["knowledge"],
                tool_tools=tools["tool"],
            ),
            state["query"],
            "supervisor",
            task_id,
        )
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        delegations = [
            _delegation(task_id, name, "completed", elapsed_ms=elapsed)
            for name in ("knowledge-agent", "tool-agent", "web-agent")
            if name.replace("-agent", "") in str(result).lower()
        ]
        logger.info("workflow.supervisor.completed task_id=%s elapsed_ms=%.1f delegations=%d", task_id, elapsed, len(delegations))
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
    logger.info("workflow.report.start task_id=%s", task_id)
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
        logger.exception("workflow.report.failed task_id=%s elapsed_ms=%.1f", task_id, (time.perf_counter() - started) * 1000)
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

from __future__ import annotations

import asyncio
import json
import logging
import time
from asyncio import to_thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import GLOBAL_TIMEOUT_SECONDS, build_workflow
from app.core.config import settings
from app.core.execution import run_with_timeout
from app.core.memory import build_short_term_context, extract_explicit_memories, render_short_term_context
from app.core.memory_store import PostgresMemoryStore
from app.core.postgres_store import PostgresTaskStore
from app.core.redis_state import get_redis_task_coordinator
from app.core.task_store import InMemoryTaskStore, TaskRecord, TaskStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    # 限制输入长度，避免超长 Prompt 放大模型和 Agent 的资源消耗。
    query: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, min_length=1, max_length=200)
    user_id: str | None = Field(default=None, min_length=1, max_length=200)


_workflow = None
_task_store: TaskStore = PostgresTaskStore() if settings.environment != "test" else InMemoryTaskStore()
_memory_store = PostgresMemoryStore()


def _get_workflow():
    global _workflow
    if _workflow is None:
        logger.info("analysis.workflow.build.start")
        started = time.perf_counter()
        _workflow = build_workflow()
        logger.info(
            "analysis.workflow.build.completed elapsed_ms=%.1f",
            (time.perf_counter() - started) * 1000,
        )
    return _workflow


def configure_task_store(store: TaskStore) -> None:
    global _task_store
    _task_store = store


def configure_memory_store(store: PostgresMemoryStore) -> None:
    global _memory_store
    _memory_store = store


def initialize_task_store() -> None:
    setup = getattr(_task_store, "setup", None)
    if callable(setup):
        started = time.perf_counter()
        logger.info("analysis.task_store.setup.start store=%s", type(_task_store).__name__)
        setup()
        logger.info(
            "analysis.task_store.setup.completed store=%s elapsed_ms=%.1f",
            type(_task_store).__name__,
            (time.perf_counter() - started) * 1000,
        )


async def _save(record: TaskRecord) -> None:
    started = time.perf_counter()
    logger.info("analysis.task_store.save.start task_id=%s status=%s", record.task_id, record.status)
    await to_thread(_task_store.save, record)
    logger.info(
        "analysis.task_store.save.completed task_id=%s status=%s elapsed_ms=%.1f",
        record.task_id,
        record.status,
        (time.perf_counter() - started) * 1000,
    )


async def _get(task_id: str) -> TaskRecord | None:
    return await to_thread(_task_store.get, task_id)


def _compact_agent_output(output: dict) -> dict:
    """Expose final evidence only; never return raw LangChain message history."""
    result = output.get("result")
    if isinstance(result, dict) and isinstance(result.get("messages"), list):
        messages = result["messages"]
        final_content = ""
        for message in reversed(messages):
            if isinstance(message, dict):
                content = message.get("content")
            else:
                content = getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                final_content = content
                break
        result = {"final_evidence": final_content}
    return {
        "agent_id": output.get("agent_id"),
        "status": output.get("status"),
        "result": result,
        "sources": output.get("sources", []),
        "errors": output.get("errors", []),
        "elapsed_ms": output.get("elapsed_ms", 0.0),
    }


async def _set_redis_status(task_id: str, status: str) -> None:
    try:
        await get_redis_task_coordinator().set_status(task_id, status)
    except Exception as exc:
        logger.warning(
            "analysis.redis_status.failed task_id=%s status=%s error_type=%s error=%s",
            task_id,
            status,
            type(exc).__name__,
            exc,
        )


async def _prepare_memory(session_id: str, user_id: str | None, query: str) -> tuple[str, str]:
    if settings.environment == "test":
        return query, str(uuid4())

    await to_thread(_memory_store.ensure_session, session_id, user_id)
    recent = await to_thread(_memory_store.recent_messages, session_id, 20)
    summary = await to_thread(_memory_store.get_summary, session_id)
    context = build_short_term_context(recent, summary=summary, limit=20)
    rendered = render_short_term_context(context)
    user_message_id = await to_thread(
        _memory_store.append_message,
        session_id,
        "user",
        query,
        user_id=user_id,
    )

    if user_id:
        memories = extract_explicit_memories(user_id, user_message_id, query)
        for memory in memories:
            await to_thread(_memory_store.upsert_long_term_memory, memory)

    enriched_query = f"{rendered}\n\n[Current User Request]\n{query}" if rendered else query
    return enriched_query, user_message_id


def _assistant_content(response: dict) -> str:
    report = response.get("report")
    if report is None:
        return ""
    if isinstance(report, str):
        return report
    if hasattr(report, "model_dump"):
        return json.dumps(report.model_dump(), ensure_ascii=False, default=str)
    return json.dumps(report, ensure_ascii=False, default=str)


async def run_analysis(query: str, *, session_id: str | None = None, user_id: str | None = None) -> dict:
    task_id = str(uuid4())
    session_id = session_id or task_id
    request_started = time.perf_counter()
    logger.info(
        "analysis.start task_id=%s session_id=%s user_id=%s query_length=%d",
        task_id,
        session_id,
        user_id or "-",
        len(query),
    )
    await _set_redis_status(task_id, "running")
    await _save(TaskRecord(task_id=task_id, status="running"))
    try:
        memory_query, _ = await _prepare_memory(session_id, user_id, query)
        logger.info(
            "analysis.memory.prepared task_id=%s session_id=%s context_length=%d",
            task_id,
            session_id,
            len(memory_query),
        )
        workflow = _get_workflow()
        workflow_started = time.perf_counter()
        result = await run_with_timeout(
            workflow.ainvoke(
                {
                    "query": memory_query,
                    "task_id": task_id,
                    "errors": [],
                    "traces": [],
                    "delegations": [],
                    "agent_outputs": [],
                },
                config={"configurable": {"thread_id": session_id}},
            ),
            timeout=GLOBAL_TIMEOUT_SECONDS,
        )
        logger.info(
            "analysis.workflow.invoke.completed task_id=%s session_id=%s elapsed_ms=%.1f errors=%d traces=%d agent_outputs=%d",
            task_id,
            session_id,
            (time.perf_counter() - workflow_started) * 1000,
            len(result.get("errors", [])),
            len(result.get("traces", [])),
            len(result.get("agent_outputs", [])),
        )
        response_agent_outputs = [_compact_agent_output(output) for output in result.get("agent_outputs", [])]
        response = {
            "task_id": task_id,
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "status": result.get("status", "completed" if not result.get("errors") else "partial"),
            "report": result.get("report"),
            "errors": result.get("errors", []),
            "traces": result.get("traces", []),
            "delegations": result.get("delegations", []),
            "agent_outputs": response_agent_outputs,
        }
        if settings.environment != "test":
            assistant_content = _assistant_content(response)
            if assistant_content:
                await to_thread(
                    _memory_store.append_message,
                    session_id,
                    "assistant",
                    assistant_content,
                    user_id=user_id,
                    metadata={"task_id": task_id, "status": response["status"]},
                )
        await _save(TaskRecord(task_id=task_id, status=response["status"], result=response))
        await _set_redis_status(task_id, response["status"])
        logger.info(
            "analysis.completed task_id=%s session_id=%s status=%s total_elapsed_ms=%.1f",
            task_id,
            session_id,
            response["status"],
            (time.perf_counter() - request_started) * 1000,
        )
        return response
    except asyncio.TimeoutError:
        await _set_redis_status(task_id, "failed")
        await _save(TaskRecord(task_id=task_id, status="failed", error=f"analysis timeout after {GLOBAL_TIMEOUT_SECONDS:.1f}s"))
        raise HTTPException(status_code=504, detail=f"analysis timed out after {GLOBAL_TIMEOUT_SECONDS:.1f}s; task_id={task_id}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis.failed task_id=%s total_elapsed_ms=%.1f error=%s", task_id, (time.perf_counter() - request_started) * 1000, exc)
        await _set_redis_status(task_id, "failed")
        await _save(TaskRecord(task_id=task_id, status="failed", error=str(exc)))
        raise


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    return await run_analysis(request.query, session_id=request.session_id, user_id=request.user_id)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    record = await _get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "task_id": record.task_id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "updated_at": record.updated_at.isoformat(),
    }

from __future__ import annotations

import logging
import time

from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_chat_model() -> ChatOpenAI:
    provider = settings.llm_provider.strip().lower()
    if provider == "qwen":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=qwen")
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL is required when LLM_PROVIDER=qwen")

    kwargs: dict = {
        "model": settings.llm_model,
        "temperature": 0,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": 0,
    }
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    logger.info(
        "llm.model.build provider=%s model=%s base_url=%s api_key_configured=%s timeout_seconds=%.1f",
        provider,
        settings.llm_model,
        settings.llm_base_url or "default",
        bool(settings.llm_api_key),
        settings.llm_timeout_seconds,
    )
    return ChatOpenAI(**kwargs)


async def ainvoke_chat_model(model: ChatOpenAI, prompt: str, *, agent_id: str, task_id: str) -> object:
    """Invoke the model with explicit start/completion/failure diagnostics."""
    started = time.perf_counter()
    logger.info(
        "llm.invoke.start task_id=%s agent=%s provider=%s model=%s prompt_length=%d",
        task_id,
        agent_id,
        settings.llm_provider,
        settings.llm_model,
        len(prompt),
    )
    try:
        response = await model.ainvoke(prompt)
        content = getattr(response, "content", None)
        logger.info(
            "llm.invoke.completed task_id=%s agent=%s elapsed_ms=%.1f response_type=%s content_length=%d",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
            type(response).__name__,
            len(str(content)) if content is not None else 0,
        )
        return response
    except Exception as exc:
        logger.exception(
            "llm.invoke.failed task_id=%s agent=%s elapsed_ms=%.1f error_type=%s error=%s",
            task_id,
            agent_id,
            (time.perf_counter() - started) * 1000,
            type(exc).__name__,
            exc,
        )
        raise

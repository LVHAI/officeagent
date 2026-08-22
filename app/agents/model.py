from __future__ import annotations

import logging

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

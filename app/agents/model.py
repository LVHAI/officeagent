from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_chat_model() -> ChatOpenAI:
    kwargs: dict = {
        "model": settings.llm_model,
        "temperature": 0,
    }
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    logger.info(
        "llm.model.build model=%s base_url=%s api_key_configured=%s",
        settings.llm_model,
        settings.llm_base_url or "default",
        bool(settings.llm_api_key),
    )
    return ChatOpenAI(**kwargs)

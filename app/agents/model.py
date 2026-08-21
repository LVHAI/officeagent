from langchain_openai import ChatOpenAI

from app.core.config import settings


def build_chat_model() -> ChatOpenAI:
    kwargs: dict = {
        "model": settings.llm_model,
        "temperature": 0,
    }
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return ChatOpenAI(**kwargs)

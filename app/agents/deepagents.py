from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

from app.agents.report_models import AnalysisReport
from app.agents.model import build_chat_model
from app.core.config import settings


SUPERVISOR_PROMPT = """
You are the Supervisor Agent for an enterprise intelligence platform.
Understand the user's intent, create an execution plan, and delegate independent
work to the minimum required specialized subagents. You may delegate to multiple
subagents when their work is independent. Preserve partial results when a
subagent fails and never fabricate missing evidence. Return source-aware results.
""".strip()

KNOWLEDGE_PROMPT = """
You are the Knowledge Agent. Execute the deterministic enterprise RAG pipeline.
Retrieve enterprise knowledge through configured knowledge tools and preserve
source metadata such as document, page, section, article, and chunk identifiers.
""".strip()

TOOL_PROMPT = """
You are the Tool Agent. Use dynamically discovered MCP skills and tools to query
enterprise systems. Select the minimum tools required, validate tool inputs,
never fabricate tool results, and preserve system, tool, request and execution
metadata. Retry transient failures only within the configured reliability policy.
""".strip()

WEB_PROMPT = """
You are the Web Agent. Use Tavily only when current or external information is
required. Filter search results, extract evidence, and preserve source URLs,
titles, and retrieval timestamps.
""".strip()

REPORT_PROMPT = """
You are the Report Agent. Aggregate validated outputs from other agents,
separate facts from recommendations, preserve citations, and explicitly list
partial or failed agent results. Never invent evidence.
""".strip()


def build_tavily_search() -> Any:
    if not settings.tavily_api_key:
        return None
    return TavilySearch(
        max_results=5,
        topic="general",
        tavily_api_key=settings.tavily_api_key,
    )


def create_supervisor(tools=None, knowledge_tools=None, tool_tools=None, web_tools=None):
    model = build_chat_model()
    web_tool = build_tavily_search() if web_tools is None else None
    external_tools = web_tools if web_tools is not None else ([web_tool] if web_tool is not None else [])
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_PROMPT,
        subagents=[
            {
                "name": "knowledge-agent",
                "description": "Retrieve and cite enterprise knowledge through the RAG pipeline.",
                "system_prompt": KNOWLEDGE_PROMPT,
                "model": model,
                "tools": knowledge_tools or [],
            },
            {
                "name": "tool-agent",
                "description": "Query enterprise systems through MCP skills and tools.",
                "system_prompt": TOOL_PROMPT,
                "model": model,
                "tools": tool_tools or tools or [],
            },
            {
                "name": "web-agent",
                "description": "Retrieve current external information with Tavily.",
                "system_prompt": WEB_PROMPT,
                "model": model,
                "tools": external_tools,
            },
        ],
    )


def create_knowledge_agent(tools=None):
    return create_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=KNOWLEDGE_PROMPT,
    )


def create_tool_agent(tools=None):
    return create_deep_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=TOOL_PROMPT,
    )


def create_web_agent(tools=None):
    web_tools = tools if tools is not None else []
    if tools is None:
        tavily = build_tavily_search()
        if tavily is not None:
            web_tools = [tavily]
    return create_agent(
        model=build_chat_model(),
        tools=web_tools,
        system_prompt=WEB_PROMPT,
    )


def create_report_agent():
    return create_agent(
        model=build_chat_model(),
        tools=[],
        system_prompt=REPORT_PROMPT,
        response_format=AnalysisReport,
    )

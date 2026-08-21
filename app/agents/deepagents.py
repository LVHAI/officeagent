from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

from app.agents.model import build_chat_model
from app.core.config import settings


# Supervisor 负责全局任务拆解和 Agent 委派；专业 Agent 不共享全部工具上下文。
SUPERVISOR_PROMPT = """
You are the Supervisor Agent for an enterprise intelligence platform.
Understand the user's intent, create an execution plan, delegate independent
work to specialized subagents, and produce a source-aware final answer.
Use the task delegation capability to select only the specialists required by
the request. Prefer parallel independent work and preserve partial results.
""".strip()

KNOWLEDGE_PROMPT = """
You are the Knowledge Agent. Execute the deterministic enterprise RAG pipeline.
Retrieve enterprise knowledge through configured knowledge tools and preserve
source metadata such as document, page, section, article, and chunk identifiers.
""".strip()

TOOL_PROMPT = """
You are the Tool Agent. Use dynamically discovered MCP skills and tools to
query enterprise systems. Select the minimum tools required for the task,
never fabricate tool results, and preserve system, tool, request and execution
metadata in your result.
""".strip()

WEB_PROMPT = """
You are the Web Agent. Use Tavily only when current or external information is
required. Filter search results, extract evidence, and preserve source URLs,
titles, and retrieval timestamps.
""".strip()

REPORT_PROMPT = """
You are the Report Agent. Aggregate validated outputs from other agents,
separate facts from recommendations, preserve source citations, and produce a
concise executive-ready report.
""".strip()


def build_tavily_search() -> Any:
    """创建 Web Agent 专用 Tavily 工具，避免把 Web Tool 暴露给 Supervisor。"""
    return TavilySearch(
        max_results=5,
        topic="general",
        tavily_api_key=settings.tavily_api_key,
    )


def create_supervisor():
    model = build_chat_model()
    # DeepAgents 的 task/subagent 能力负责 Agentic Delegation；LangGraph 负责外层状态和执行。
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_PROMPT,
        subagents=[
            {
                "name": "knowledge-agent",
                "description": "Retrieve and cite enterprise knowledge through the RAG pipeline.",
                "system_prompt": KNOWLEDGE_PROMPT,
                "model": model,
                "tools": [],
            },
            {
                "name": "tool-agent",
                "description": "Query enterprise systems through MCP skills and tools.",
                "system_prompt": TOOL_PROMPT,
                "model": model,
                "tools": [],
            },
            {
                "name": "web-agent",
                "description": "Retrieve current external information with Tavily.",
                "system_prompt": WEB_PROMPT,
                "model": model,
                "tools": [build_tavily_search()],
            },
        ],
    )


def create_knowledge_agent(tools=None):
    # RAG 流程保持确定性，不为了“Agent”概念额外引入 DeepAgents Loop。
    return create_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=KNOWLEDGE_PROMPT,
    )


def create_tool_agent(tools=None):
    # Tool Agent 需要动态选择 MCP Tool 并进行多步工具编排，因此使用 DeepAgents。
    return create_deep_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=TOOL_PROMPT,
        skills=["./skills/sql"],
    )


def create_web_agent(tools=None):
    # Web Agent 只暴露 Tavily，保持搜索流程简单、可测试、可替换。
    web_tools = tools if tools is not None else [build_tavily_search()]
    return create_agent(
        model=build_chat_model(),
        tools=web_tools,
        system_prompt=WEB_PROMPT,
    )


def create_report_agent():
    # 报告生成使用普通 Agent Runtime，后续可通过 response_format 增加结构化输出。
    return create_agent(
        model=build_chat_model(),
        tools=[],
        system_prompt=REPORT_PROMPT,
    )

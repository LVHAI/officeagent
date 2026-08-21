from __future__ import annotations

from deepagents import create_deep_agent

from app.agents.model import build_chat_model


# Supervisor 负责任务拆解和 Agent 委派；具体执行交给专业子 Agent。
SUPERVISOR_PROMPT = """
You are the Supervisor Agent for an enterprise intelligence platform.
Understand the user's intent, create an execution plan, delegate independent
work to specialized subagents, and produce a source-aware final answer.
Prefer parallel independent work and preserve partial results when one worker fails.
""".strip()


# 知识 Agent 只处理企业知识检索，并要求保留可追溯的文档定位信息。
KNOWLEDGE_PROMPT = """
You are the Knowledge Agent. Retrieve enterprise knowledge through the
configured knowledge tools. Every factual answer must preserve document,
page, section, article, and chunk identifiers when available.
""".strip()


# Tool Agent 通过 MCP 使用企业系统能力，禁止根据上下文臆造工具结果。
TOOL_PROMPT = """
You are the Tool Agent. Use dynamically discovered MCP skills and tools to
query enterprise systems. Never fabricate tool results and always preserve
system, tool, request and execution metadata.
""".strip()


WEB_PROMPT = """
You are the Web Agent. Retrieve external information only when the task
requires current or external context. Preserve source URLs and timestamps.
""".strip()


REPORT_PROMPT = """
You are the Report Agent. Aggregate validated outputs from other agents,
separate facts from recommendations, preserve source citations, and produce
a concise executive-ready report.
""".strip()


def create_supervisor():
    model = build_chat_model()
    # DeepAgents 的 subagents 机制负责 Multi-Agent 委派；LangGraph 不负责替代它。
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_PROMPT,
        skills=["./skills/crm", "./skills/sql", "./skills/report"],
        subagents=[
            {
                "name": "knowledge-agent",
                "description": "Retrieve and cite enterprise knowledge.",
                "system_prompt": KNOWLEDGE_PROMPT,
                "model": model,
            },
            {
                "name": "tool-agent",
                "description": "Query enterprise systems through MCP skills and tools.",
                "system_prompt": TOOL_PROMPT,
                "model": model,
            },
            {
                "name": "web-agent",
                "description": "Retrieve external information and preserve sources.",
                "system_prompt": WEB_PROMPT,
                "model": model,
            },
        ],
    )


def create_knowledge_agent(tools=None):
    return create_deep_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=KNOWLEDGE_PROMPT,
        skills=["./skills/crm"],
    )


def create_tool_agent(tools=None):
    return create_deep_agent(
        model=build_chat_model(),
        tools=tools or [],
        system_prompt=TOOL_PROMPT,
        skills=["./skills/sql"],
    )


def create_web_agent(tools=None):
    return create_deep_agent(model=build_chat_model(), tools=tools or [], system_prompt=WEB_PROMPT)


def create_report_agent():
    return create_deep_agent(
        model=build_chat_model(),
        system_prompt=REPORT_PROMPT,
        skills=["./skills/report"],
    )

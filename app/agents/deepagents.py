from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.agents.report_models import AnalysisReport, ReportFinding, ReportSource
from app.agents.model import build_chat_model, ainvoke_chat_model
from app.core.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_PATH = "/skills/"
CRM_DIRECT_TOOL_NAMES = {"customer_query", "customer_search", "customer_lookup"}


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
enterprise systems. Load the relevant project skill before choosing a tool.
For CRM requests, the CRM skill is authoritative: use the Database MCP sql_query
tool for read-only PostgreSQL access and do not use direct CRM/customer query
tools. Select the minimum tools required, validate tool inputs, never fabricate
tool results, and preserve system, tool, request and execution metadata.
Retry transient failures only within the configured reliability policy.
""".strip()

WEB_PROMPT = """
You are the Web Agent. Use Tavily only when current or external information is
required. Filter search results, extract evidence, and preserve source URLs,
titles, and retrieval timestamps.
""".strip()

REPORT_PROMPT = """
You are the Report Agent. Aggregate validated outputs from other agents.
You MUST call the submit_analysis_report tool exactly once with the final report.
Do not return a report as free-form JSON or Markdown. Do not invent evidence.
Separate facts from recommendations, preserve citations, and explicitly list
partial or failed agent results. Confidence must be between 0 and 1.
""".strip()


@tool
def submit_analysis_report(
    summary: str,
    findings: list[ReportFinding],
    recommendations: list[str],
    sources: list[ReportSource],
    partial_results: list[str],
) -> str:
    """Submit the final validated enterprise analysis report."""
    return "analysis report accepted"


def build_tavily_search() -> Any:
    if not settings.tavily_api_key:
        return None
    return TavilySearch(
        max_results=5,
        topic="general",
        tavily_api_key=settings.tavily_api_key,
    )


def build_agent_backend() -> Any:
    """Keep project Skills on the real filesystem while agent work stays ephemeral."""
    return CompositeBackend(
        default=StateBackend(),
        routes={
            SKILLS_PATH: FilesystemBackend(
                root_dir=str(PROJECT_ROOT),
                virtual_mode=True,
            ),
        },
    )


def _filter_tool_agent_tools(tool_tools: list[Any]) -> list[Any]:
    """Prevent direct CRM MCP tools from competing with the CRM Skill workflow.

    CRM/customer query endpoints are intentionally hidden from Tool Agent. CRM
    requests must use the domain Skill and Database MCP sql_query path.
    """
    selected: list[Any] = []
    filtered: list[str] = []
    for candidate in tool_tools:
        name = getattr(candidate, "name", "")
        if name in CRM_DIRECT_TOOL_NAMES:
            filtered.append(name)
            continue
        selected.append(candidate)
    if filtered:
        logger.info("agent.tools.crm_direct_filtered tools=%s", sorted(filtered))
    return selected


def create_supervisor(tools=None, knowledge_tools=None, tool_tools=None, web_tools=None):
    model = build_chat_model()
    web_tool = build_tavily_search() if web_tools is None else None
    external_tools = web_tools if web_tools is not None else ([web_tool] if web_tool is not None else [])
    selected_tool_tools = _filter_tool_agent_tools(tool_tools or tools or [])
    logger.info(
        "agent.create supervisor model=%s knowledge_tools=%d tool_tools=%d web_tools=%d skills=%s",
        settings.llm_model,
        len(knowledge_tools or []),
        len(selected_tool_tools),
        len(external_tools),
        SKILLS_PATH,
    )
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_PROMPT,
        backend=build_agent_backend(),
        skills=[SKILLS_PATH],
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
                "tools": selected_tool_tools,
                "skills": [SKILLS_PATH],
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
    return create_agent(model=build_chat_model(), tools=tools or [], system_prompt=KNOWLEDGE_PROMPT)

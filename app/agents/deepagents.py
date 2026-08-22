from __future__ import annotations

import logging
import time
from typing import Any

from deepagents import create_deep_agent
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.agents.report_models import AnalysisReport, ReportFinding, ReportSource
from app.agents.model import build_chat_model, ainvoke_chat_model
from app.core.config import settings

logger = logging.getLogger(__name__)


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


def create_supervisor(tools=None, knowledge_tools=None, tool_tools=None, web_tools=None):
    model = build_chat_model()
    web_tool = build_tavily_search() if web_tools is None else None
    external_tools = web_tools if web_tools is not None else ([web_tool] if web_tool is not None else [])
    logger.info(
        "agent.create supervisor model=%s knowledge_tools=%d tool_tools=%d web_tools=%d",
        settings.llm_model,
        len(knowledge_tools or []),
        len(tool_tools or tools or []),
        len(external_tools),
    )
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
    return create_agent(model=build_chat_model(), tools=tools or [], system_prompt=KNOWLEDGE_PROMPT)


def create_tool_agent(tools=None):
    return create_deep_agent(model=build_chat_model(), tools=tools or [], system_prompt=TOOL_PROMPT)


def create_web_agent(tools=None):
    web_tools = tools if tools is not None else []
    if tools is None:
        tavily = build_tavily_search()
        if tavily is not None:
            web_tools = [tavily]
    return create_agent(model=build_chat_model(), tools=web_tools, system_prompt=WEB_PROMPT)


class _ReportAgent:
    """Adapter exposing the same ainvoke contract used by graph._invoke."""

    def __init__(self, model: Any):
        self._model = model
        self._tool_model = model.bind_tools(
            [submit_analysis_report],
            tool_choice="submit_analysis_report",
        )

    @staticmethod
    def _extract_report(response: Any) -> AnalysisReport:
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            raise ValueError("Report Agent did not call submit_analysis_report")

        if len(tool_calls) != 1:
            raise ValueError(
                f"Report Agent must call submit_analysis_report exactly once; got {len(tool_calls)}"
            )

        call = tool_calls[0]
        name = call.get("name")
        if name != "submit_analysis_report":
            raise ValueError(f"Unexpected Report Agent tool call: {name!r}")

        args = call.get("args")
        if not isinstance(args, dict):
            raise ValueError("submit_analysis_report tool arguments must be an object")

        try:
            return AnalysisReport.model_validate(args)
        except Exception as exc:
            logger.exception(
                "report.validation.failed tool=submit_analysis_report error_type=%s error=%s",
                type(exc).__name__,
                exc,
            )
            raise

    async def ainvoke(self, request: dict[str, Any]) -> AnalysisReport:
        task_id = str(request.get("task_id", "unknown"))
        messages = request.get("messages", [])
        context = messages[-1].get("content", "") if messages else ""
        logger.info(
            "report.invoke.start task_id=%s model=%s context_length=%d tool=submit_analysis_report",
            task_id,
            settings.llm_model,
            len(str(context)),
        )

        started = time.perf_counter()
        try:
            response = await ainvoke_chat_model(
                self._tool_model,
                f"{REPORT_PROMPT}\n\nValidated context:\n{context}",
                agent_id="report",
                task_id=task_id,
            )
            tool_calls = getattr(response, "tool_calls", None) or []
            logger.info(
                "report.tool_call.received task_id=%s call_count=%d names=%s",
                task_id,
                len(tool_calls),
                [call.get("name") for call in tool_calls],
            )
            report = self._extract_report(response)
        except Exception as exc:
            logger.exception(
                "report.invoke.failed task_id=%s elapsed_ms=%.1f error_type=%s error=%s",
                task_id,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            raise

        logger.info(
            "report.invoke.completed task_id=%s elapsed_ms=%.1f findings=%d recommendations=%d sources=%d partial_results=%d",
            task_id,
            (time.perf_counter() - started) * 1000,
            len(report.findings),
            len(report.recommendations),
            len(report.sources),
            len(report.partial_results),
        )
        return report


def create_report_agent():
    logger.info("agent.create report model=%s tool=submit_analysis_report", settings.llm_model)
    return _ReportAgent(build_chat_model())

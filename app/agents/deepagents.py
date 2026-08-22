from __future__ import annotations

import json
import logging
import time
from typing import Any

from deepagents import create_deep_agent
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

from app.agents.report_models import AnalysisReport
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
Return ONLY one JSON object matching exactly this schema:
{
  "summary": "string",
  "findings": [{"title": "string", "evidence": "string", "confidence": 0.0}],
  "recommendations": ["string"],
  "sources": [{"kind": "string", "title": "string", "uri": "string"}],
  "partial_results": ["string"]
}
The keys must be exactly: summary, findings, recommendations, sources, partial_results.
Do not add report_id, title, date_generated, executive_summary, detailed_analysis,
or any other top-level fields. recommendations MUST be an array of strings.
findings MUST be an array of objects. sources MUST be an array of objects.
Separate facts from recommendations, preserve citations, and explicitly list
partial or failed agent results. Never invent evidence. Confidence must be a
number between 0 and 1. Do not wrap the JSON in Markdown fences.
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


def _report_json_prompt(context: str) -> str:
    return (
        "Produce the final enterprise analysis report from the validated context below. "
        "Return only one JSON object matching EXACTLY the five-key Report Agent schema "
        "in the system prompt. Do not use an alternative report schema.\n\n"
        f"Context:\n{context}"
    )


def _coerce_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common Qwen/report-template variants into the internal schema."""
    if "summary" not in payload and payload.get("executive_summary") is not None:
        payload["summary"] = payload["executive_summary"]

    recommendations = payload.get("recommendations", [])
    if isinstance(recommendations, str):
        payload["recommendations"] = [recommendations]
    elif recommendations is None:
        payload["recommendations"] = []

    findings = payload.get("findings")
    if findings is None:
        findings = []
        detailed = payload.get("detailed_analysis")
        if isinstance(detailed, dict):
            for key, value in detailed.items():
                if isinstance(value, str):
                    findings.append({"title": str(key), "evidence": value, "confidence": 1.0})
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            title = item.get("capability") or item.get("title") or str(key)
                            evidence = item.get("description") or item.get("evidence") or json.dumps(item, ensure_ascii=False)
                            findings.append({"title": str(title), "evidence": str(evidence), "confidence": 1.0})
                        elif item is not None:
                            findings.append({"title": str(key), "evidence": str(item), "confidence": 1.0})
                elif value is not None:
                    findings.append({"title": str(key), "evidence": str(value), "confidence": 1.0})
        payload["findings"] = findings

    if payload.get("sources") is None:
        payload["sources"] = []
    if payload.get("partial_results") is None:
        payload["partial_results"] = []

    return payload


def _parse_report_response(content: Any) -> AnalysisReport:
    if isinstance(content, dict):
        return AnalysisReport.model_validate(_coerce_report_payload(dict(content)))
    text = str(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Report Agent returned non-JSON output")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Report Agent JSON root must be an object")
    return AnalysisReport.model_validate(_coerce_report_payload(payload))


class _ReportAgent:
    """Adapter exposing the same ainvoke contract used by graph._invoke."""

    def __init__(self, model: Any):
        self._model = model

    async def ainvoke(self, request: dict[str, Any]) -> AnalysisReport:
        task_id = str(request.get("task_id", "unknown"))
        messages = request.get("messages", [])
        context = messages[-1].get("content", "") if messages else ""
        logger.info(
            "report.invoke.start task_id=%s model=%s context_length=%d",
            task_id,
            settings.llm_model,
            len(str(context)),
        )
        prompt = _report_json_prompt(str(context))
        logger.info("report.prompt.ready task_id=%s prompt_length=%d", task_id, len(prompt))
        started = time.perf_counter()
        response = await ainvoke_chat_model(self._model, prompt, agent_id="report", task_id=task_id)
        content = getattr(response, "content", "")
        logger.info(
            "report.response.received task_id=%s elapsed_ms=%.1f content_length=%d",
            task_id,
            (time.perf_counter() - started) * 1000,
            len(str(content)),
        )
        try:
            report = _parse_report_response(content)
        except Exception as exc:
            logger.exception(
                "report.response.parse_failed task_id=%s content_preview=%r error=%s",
                task_id,
                str(content)[:500],
                exc,
            )
            raise
        logger.info(
            "report.invoke.completed task_id=%s elapsed_ms=%.1f findings=%d recommendations=%d sources=%d",
            task_id,
            (time.perf_counter() - started) * 1000,
            len(report.findings),
            len(report.recommendations),
            len(report.sources),
        )
        return report


def create_report_agent():
    logger.info("agent.create report model=%s", settings.llm_model)
    return _ReportAgent(build_chat_model())

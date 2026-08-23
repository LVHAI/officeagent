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

from app.agents.mcp_registry import mcp_registry
from app.agents.report_models import AnalysisReport, ReportFinding, ReportSource
from app.agents.model import build_chat_model, ainvoke_chat_model
from app.agents.skills import build_skill_runtime_tools, load_skill_metadata
from app.core.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_PATH = "/skills/"
SKILL_REGISTRY = load_skill_metadata(PROJECT_ROOT / "skills")
CANONICAL_SKILL_NAMES = ", ".join(sorted(skill.name for skill in SKILL_REGISTRY.all())) or "<none>"


SUPERVISOR_PROMPT = """
You are the Supervisor Agent for an enterprise intelligence platform.
You are the Multi-Agent planning and delegation center. Understand the user's intent,
create an execution plan, and delegate work to the minimum required specialized
subagents. Do not execute enterprise business-data work yourself.

Routing rules are mandatory:
- Enterprise live/transactional/business data queries MUST delegate to tool-agent.
- Customer, CRM, order, sales, finance, ERP, inventory, or other enterprise-system
  data requests are Tool Agent work even when the request sounds like a knowledge
  question. Do NOT delegate these requests to knowledge-agent merely because the
  request contains words such as "query", "information", or "analysis".
- Knowledge-agent is only for enterprise documents/knowledge/RAG content such as
  policies, manuals, contracts, product documents, FAQs, and internal knowledge.
- web-agent is only for current/external web information.
- If a request combines independent knowledge and enterprise-data work, delegate
  only the necessary agents; do not call every agent by default.
- For a clearly enterprise-data-only request, tool-agent should normally be the
  only specialized subagent delegated before reporting.

Preserve partial results when a subagent fails and never fabricate missing evidence.
Return source-aware results. Let Tool Agent perform Skill Selection and MCP Tool
Selection; the Supervisor must not depend on concrete MCP Tool schemas.
""".strip()

KNOWLEDGE_PROMPT = """
You are the Knowledge Agent. Execute the deterministic enterprise RAG pipeline.
Retrieve enterprise knowledge through configured knowledge tools and preserve
source metadata such as document, page, section, article, and chunk identifiers.
""".strip()

TOOL_PROMPT = f"""
You are the Tool Agent. Skills are the only business routing layer for enterprise
MCP access. First inspect the available Skill metadata and select exactly the Skill
that best matches the user's intent. The canonical Skill names currently available
are: {CANONICAL_SKILL_NAMES}. You MUST use one of these canonical names when calling
Skill Runtime tools; do not invent descriptive Skill IDs such as
"crm_customer_info_skill". If a natural-language Skill description suggests an
alias, resolve it to the canonical Skill name first.

Then read that Skill's SKILL.md instructions. The selected Skill declares which MCP
server and MCP tools are allowed.

After selecting the Skill:
1. Read the selected Skill's complete SKILL.md instructions.
2. Call `discover_skill_mcp_tools` for that Skill before any MCP invocation.
3. Select the minimum MCP tool(s) required by the task from the discovered schemas.
4. Call `invoke_skill_mcp_tool` only with the selected Skill and a discovered,
   Skill-authorized tool name.
5. Interpret and preserve the returned evidence; never fabricate results.

Never select tools by matching raw MCP names before selecting a Skill. Never assume
CRM means SQL or any other implementation; follow the selected Skill exactly.
Do not call every discovered tool. For a simple customer lookup, use the minimum
single MCP operation that answers the request. Only use multiple MCP calls when the
selected Skill instructions and the user's request require independent facts that
cannot reasonably be obtained together.

The concrete enterprise MCP tools are intentionally NOT registered in your Agent
context. The two Skill Runtime tools are the only MCP access mechanism. Never bypass
Skill selection or invoke a concrete MCP tool directly.
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


def create_supervisor(tools=None, knowledge_tools=None, tool_tools=None, web_tools=None):
    model = build_chat_model()
    web_tool = build_tavily_search() if web_tools is None else None
    external_tools = web_tools if web_tools is not None else ([web_tool] if web_tool is not None else [])
    skill_runtime_tools = build_skill_runtime_tools(SKILL_REGISTRY, mcp_registry.get_client)
    logger.info(
        "agent.create supervisor model=%s knowledge_tools=%d tool_agent_tools=%d web_tools=%d tool_agent_skills=%s",
        settings.llm_model,
        len(knowledge_tools or []),
        len(skill_runtime_tools),
        len(external_tools),
        SKILLS_PATH,
    )
    return create_deep_agent(
        model=model,
        system_prompt=SUPERVISOR_PROMPT,
        backend=build_agent_backend(),
        subagents=[
            {
                "name": "knowledge-agent",
                "description": "Retrieve and cite enterprise knowledge through the RAG pipeline. Do not use for live CRM, sales, order, finance, ERP, inventory, or other enterprise-system data.",
                "system_prompt": KNOWLEDGE_PROMPT,
                "model": model,
                "tools": knowledge_tools or [],
            },
            {
                "name": "tool-agent",
                "description": f"Handle live enterprise business data. Select exactly one matching Skill from [{CANONICAL_SKILL_NAMES}], read its SKILL.md, then dynamically discover and invoke only that Skill's authorized MCP tools.",
                "system_prompt": TOOL_PROMPT,
                "model": model,
                "tools": skill_runtime_tools,
                "skills": [SKILLS_PATH],
            },
            {
                "name": "web-agent",
                "description": "Retrieve current external information with Tavily. Do not use for internal enterprise-system data.",
                "system_prompt": WEB_PROMPT,
                "model": model,
                "tools": external_tools,
            },
        ],
    )


def create_knowledge_agent(tools=None):
    return create_agent(model=build_chat_model(), tools=tools or [], system_prompt=KNOWLEDGE_PROMPT)


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

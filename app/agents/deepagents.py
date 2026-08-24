from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool, tool
from langchain_tavily import TavilySearch

from app.agents.knowledge import knowledge_search
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


KNOWLEDGE_PROMPT = """
You are the Knowledge Agent. Your only retrieval mechanism is the configured
Knowledge Base RAG pipeline. Call the knowledge_search tool for every knowledge
retrieval task. Never call MCP, enterprise Skills, CRM/database tools, or web search.
The knowledge_search tool performs query rewrite, BM25 retrieval, optional Milvus
vector retrieval, reranking, and source-aware context construction.

The Knowledge Base is heterogeneous and can contain different kinds of internal
knowledge. Current examples include:
- Recipes and cooking documents, such as "咖喱炒蟹的做法".
- Laws and regulations, including "中华人民共和国劳动法" and
  "中华人民共和国劳动合同法".
- Policy and other structured article documents.
- Parent-child Markdown documents and other domain-specific business or reference
  documents.

Do not assume that all documents use the same structure. Determine the likely
knowledge type from the user's question and use the retrieved evidence rather than
assuming a document exists merely because a type or example is listed above.

For legal or policy questions, pay particular attention to the document name and
article number, because different laws can contain the same article numbers. For
parent-child documents, preserve the relationship between the matched child section
and its parent context when that context is needed to answer the question.

Use the returned context as evidence. Preserve document, page, section, article,
chunk, score, and route metadata. If the RAG result is empty or does not contain
sufficient evidence, explicitly report that no relevant Knowledge Base evidence was
found instead of inventing a source or relying on model memory.

Return only the evidence and concise answer context needed by downstream agents.
Do not return unnecessary raw chunks or unrelated retrieved documents.
""".strip()

TOOL_PROMPT = f"""
You are the Tool Agent. Skills are the only business routing layer for enterprise
MCP access. First inspect the available Skill metadata and select exactly the Skill
that best matches the user's intent. The canonical Skill names currently available
are: {CANONICAL_SKILL_NAMES}. You MUST use one of these canonical names when calling
Skill Runtime tools; do not invent descriptive Skill IDs such as
"crm_customer_info_skill". If a natural-language Skill description suggests an alias,
resolve it to the canonical Skill name first.

The Skill Runtime is the authoritative way to load Skill instructions. Do NOT assume
that the filesystem Skill mount has been read merely because `/skills/` is available.
After selecting the Skill, call `discover_skill_mcp_tools` first. Its response contains
both the complete selected Skill instructions from SKILL.md and the discovered MCP
schemas. Treat the returned Skill instructions as mandatory execution policy.

Execution sequence is mandatory:
1. Select exactly one canonical Skill that matches the user's enterprise-data intent.
2. Call `discover_skill_mcp_tools` for that Skill before any MCP invocation.
3. Read and apply the COMPLETE `instructions` returned by the discovery call. This
   includes the Skill's responsibilities, schema guidance, query examples, safety
   rules, and tool policy. Do not substitute generic SQL knowledge for Skill rules.
4. Select the minimum MCP tool(s) required by the task from the discovered schemas.
5. Construct arguments strictly from the selected Skill instructions and discovered
   MCP input schema. Never invent table names or column names when the Skill provides
   them.
6. Call `invoke_skill_mcp_tool` only with the selected Skill and a discovered,
   Skill-authorized tool name.
7. Interpret and preserve the returned evidence; never fabricate results.

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
You are the Web Agent. Use the web_search tool only when current or external
information is required. For a delegated Web task, you MUST call web_search before
producing an answer. If web_search fails or is unavailable, report the failure and do
not substitute model memory or fabricate current facts. Filter search results, extract
evidence, and preserve source URLs, titles, and retrieval timestamps. Do not use Web
Search for internal Knowledge Base retrieval; that belongs to Knowledge Agent.
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
    client = None
    if settings.tavily_api_key:
        client = TavilySearch(
            max_results=5,
            topic="general",
            tavily_api_key=settings.tavily_api_key,
        )
    else:
        logger.warning("web.search.unavailable reason=tavily_api_key_missing")

    async def search(query: str) -> Any:
        started = time.perf_counter()
        logger.info(
            "web.search.start query=%s provider=tavily configured=%s",
            query,
            bool(client),
        )
        if client is None:
            error = "Tavily search is unavailable because TAVILY_API_KEY is not configured"
            logger.error(
                "web.search.failed query=%s elapsed_ms=%.1f error_type=ConfigurationError error=%s",
                query,
                (time.perf_counter() - started) * 1000,
                error,
            )
            raise RuntimeError(error)

        try:
            result = await client.ainvoke({"query": query})
            if isinstance(result, dict):
                result_count = len(result.get("results", []))
            elif isinstance(result, list):
                result_count = len(result)
            else:
                result_count = 1
            logger.info(
                "web.search.completed query=%s result_count=%d elapsed_ms=%.1f",
                query,
                result_count,
                (time.perf_counter() - started) * 1000,
            )
            return result
        except Exception as exc:
            logger.exception(
                "web.search.failed query=%s elapsed_ms=%.1f error_type=%s error=%s",
                query,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            raise

    return StructuredTool.from_function(
        coroutine=search,
        name="web_search",
        description="MANDATORY for delegated current/external research. Search the current public web with Tavily and return source-aware results.",
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


def create_knowledge_agent(tools=None):
    return create_agent(
        model=build_chat_model(),
        tools=tools or [knowledge_search],
        system_prompt=KNOWLEDGE_PROMPT,
    )


def create_tool_agent(tools=None):
    model = build_chat_model()
    runtime_tools = tools or build_skill_runtime_tools(SKILL_REGISTRY, mcp_registry.get_client)
    return create_deep_agent(
        model=model,
        system_prompt=TOOL_PROMPT,
        backend=build_agent_backend(),
        tools=runtime_tools,
        skills=[SKILLS_PATH],
    )


def create_web_agent(tools=None):
    runtime_tools = tools if tools is not None else [build_tavily_search()]
    return create_agent(model=build_chat_model(), tools=runtime_tools, system_prompt=WEB_PROMPT)


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
        return AnalysisReport.model_validate(args)

    async def ainvoke(self, request: dict[str, Any]) -> AnalysisReport:
        task_id = str(request.get("task_id", "unknown"))
        messages = request.get("messages", [])
        context = messages[-1].get("content", "") if messages else ""
        started = time.perf_counter()
        logger.info(
            "report.invoke.start task_id=%s model=%s context_length=%d tool=submit_analysis_report",
            task_id,
            settings.llm_model,
            len(str(context)),
        )
        try:
            response = await ainvoke_chat_model(
                self._tool_model,
                f"{REPORT_PROMPT}\n\nValidated context:\n{context}",
                agent_id="report",
                task_id=task_id,
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

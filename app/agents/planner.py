from __future__ import annotations

import json
import logging
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from app.agents.execution_plan import ExecutionPlan
from app.agents.model import build_chat_model

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """
You are the Supervisor DeepAgent for an enterprise intelligence platform.
You are the sole planning and delegation decision center. You must not answer the
user's question and you must not execute any child agent, MCP tool, RAG retrieval,
or web search yourself.

You MUST call submit_execution_plan exactly once. Create the minimum plan that can
answer the user's request. Do NOT add a specialist merely because the final task is
an analysis or synthesis task.

The submit_execution_plan function is the authoritative structured function-calling
interface. Use ONLY these agent values: knowledge-agent, tool-agent, web-agent.
NEVER emit general-purpose, general-purpose-agent, knowledge, tool, web, or any other
agent name. For optional fields, prefer omitting them rather than emitting null.
Never invent database fields, product names, or facts not present in the user request
or available context.

Delegation rules:
- Internal Knowledge Base evidence, manuals, policies, FAQs, recipes, product
  documentation, or internal documents -> knowledge-agent.
- Current or external internet evidence -> web-agent.
- Enterprise live/transactional data such as CRM, customer, orders, sales, finance,
  ERP, and inventory -> tool-agent.
- Mixed requests may use multiple agents. Independent tasks must omit dependencies
  and should share a parallel group. Add dependencies only when one task genuinely
  requires another specialist's intermediate result.
- Knowledge Agent, Tool Agent, and Web Agent are independent specialist branches by
  default. When multiple branches are required, delegate them independently so
  LangGraph can execute them concurrently.
- Do NOT use depends_on to represent final synthesis, comparison, or analysis-together.
  Cross-agent synthesis belongs to Aggregation / Report after specialist execution.
- Never select all agents by default. Every selected agent must have a concrete
  evidence requirement in the user's request.
- The Tool Agent decides Skill -> MCP internally; do not mention or invent concrete
  MCP tool names in the plan.
- The Knowledge Agent owns the RAG pipeline directly.
- If current external information is required, web-agent is required even when the
  request also needs enterprise data.
- On replanning, create work only for missing or failed evidence. Do not repeat
  successful work unless the failed work makes it necessary.

The final decision about which child agents to call belongs to you. Do not rely on a
Python keyword router or deterministic post-processing to rewrite a valid plan.
""".strip()

_AGENT_ALIASES = {
    "knowledge": "knowledge-agent",
    "knowledge_agent": "knowledge-agent",
    "knowledge-agent": "knowledge-agent",
    "tool": "tool-agent",
    "tool_agent": "tool-agent",
    "tool-agent": "tool-agent",
    "general-purpose": "tool-agent",
    "general_purpose": "tool-agent",
    "general-purpose-agent": "tool-agent",
    "web": "web-agent",
    "web_agent": "web-agent",
    "web-agent": "web-agent",
}


def _normalize_agent_alias(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _AGENT_ALIASES.get(value, value)


class PlannerTaskInput(BaseModel):
    """Model-facing schema tolerant of known LLM routing aliases."""

    task_id: str = Field(min_length=1)
    agent: str
    query: str = Field(min_length=1)
    depends_on: list[str] | None = None
    parallel_group: str | None = None
    constraints: dict[str, object] | None = None

    @field_validator("agent", mode="before")
    @classmethod
    def normalize_agent(cls, value: Any) -> Any:
        return _normalize_agent_alias(value)


class PlannerInput(BaseModel):
    """Function-calling schema; canonical validation happens before execution."""

    tasks: list[PlannerTaskInput] = Field(min_length=1, max_length=12)
    rationale: str | None = None


def submit_execution_plan(
    tasks: list[dict[str, Any]], rationale: str | None = None
) -> str:
    """Function-calling entry point with canonical ExecutionPlan validation."""
    payload = PlannerInput(tasks=tasks, rationale=rationale)
    plan = ExecutionPlan.model_validate(payload.model_dump())
    return plan.model_dump_json()


PLAN_TOOL = StructuredTool.from_function(
    func=submit_execution_plan,
    name="submit_execution_plan",
    description=(
        "Submit exactly one validated execution plan. Each task should use "
        "knowledge-agent, tool-agent, or web-agent."
    ),
    args_schema=PlannerInput,
)


class _PlannerAgent:
    def __init__(self) -> None:
        self._agent = create_deep_agent(
            model=build_chat_model(),
            system_prompt=PLANNER_PROMPT,
            tools=[PLAN_TOOL],
            backend=CompositeBackend(default=StateBackend(), routes={}),
        )

    async def ainvoke(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self._agent.ainvoke(request)


def create_supervisor() -> _PlannerAgent:
    """Create the single Supervisor DeepAgent used by the LangGraph workflow."""
    logger.info("agent.create supervisor model=deepagent role=planner")
    return _PlannerAgent()


def create_execution_planner() -> _PlannerAgent:
    """Backward-compatible alias for the canonical Supervisor factory."""
    return create_supervisor()


def _message_value(message: Any, key: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def _tool_call_args(call: Any) -> dict[str, Any]:
    args = _message_value(call, "args", {})
    if not isinstance(args, dict):
        raise ValueError("submit_execution_plan arguments must be an object")
    return args


def _tool_message_plan(message: Any) -> dict[str, Any] | None:
    name = _message_value(message, "name") or _message_value(message, "tool_name")
    if name != "submit_execution_plan":
        return None
    content = _message_value(message, "content")
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
    return None


def _normalize_tool_call(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize known LLM aliases before strict ExecutionPlan validation."""
    normalized = dict(value)
    tasks = normalized.get("tasks")
    if isinstance(tasks, list):
        normalized["tasks"] = [
            {
                **task,
                "agent": _normalize_agent_alias(task.get("agent")),
            }
            if isinstance(task, dict) else task
            for task in tasks
        ]
    return normalized


def _normalize_plan(value: dict[str, Any]) -> ExecutionPlan:
    return ExecutionPlan.model_validate(_normalize_tool_call(value))


def extract_execution_plan(result: Any) -> ExecutionPlan:
    """Extract and canonicalize the Supervisor's structured function call."""
    messages = result.get("messages", []) if isinstance(result, dict) else []
    submitted: list[ExecutionPlan] = []

    for message in messages:
        tool_calls = (
            message.get("tool_calls", [])
            if isinstance(message, dict)
            else getattr(message, "tool_calls", [])
        )
        for call in tool_calls or []:
            if _message_value(call, "name") == "submit_execution_plan":
                submitted.append(_normalize_plan(_tool_call_args(call)))

        tool_plan = _tool_message_plan(message)
        if tool_plan is not None:
            submitted.append(_normalize_plan(tool_plan))

    if not submitted:
        raise ValueError(
            "Supervisor must call submit_execution_plan exactly once; no submitted plan was found"
        )

    first = submitted[0]
    canonical = first.model_dump(mode="json")
    if any(plan.model_dump(mode="json") != canonical for plan in submitted[1:]):
        logger.error(
            "supervisor.plan.conflict count=%d plans=%s",
            len(submitted), [plan.model_dump(mode="json") for plan in submitted],
        )
        raise ValueError(
            "Supervisor submitted multiple different execution plans; refusing to choose silently"
        )

    if len(submitted) > 1:
        logger.info(
            "supervisor.plan.duplicate_representations count=%d action=deduplicated",
            len(submitted),
        )

    return first

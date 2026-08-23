from __future__ import annotations

import json
import logging
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from langchain_core.tools import StructuredTool

from app.agents.execution_plan import ExecutionPlan
from app.agents.model import build_chat_model

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """
You are the Supervisor Agent for an enterprise intelligence platform. You are ONLY a
planner. You must not answer the user's question and you must not execute any child
agent, MCP tool, RAG retrieval, or web search yourself.

You MUST call submit_execution_plan exactly once. Create the minimum plan that can
answer the user's request.

Routing rules:
- Internal knowledge, manuals, policies, FAQs, recipes, product documentation and
  questions answerable from the configured Knowledge Base -> knowledge-agent.
- Current or external internet information -> web-agent.
- Enterprise live/transactional data such as CRM, customer, orders, sales, finance,
  ERP and inventory -> tool-agent.
- Mixed requests may use multiple agents. Independent tasks should share a parallel
  group and omit dependencies. Only add dependencies when one task genuinely needs
  another task's result.
- Never select all agents by default.
- The Tool Agent decides Skill -> MCP internally; do not mention or invent MCP tool
  names in the plan.
- The Knowledge Agent owns the RAG pipeline directly.
- If the request asks for current external information, web-agent is required even
  if the request also needs enterprise data.
""".strip()


def submit_execution_plan(tasks: list[dict[str, Any]], rationale: str = "") -> str:
    """Validate and accept the Supervisor's execution plan."""
    plan = ExecutionPlan(tasks=tasks, rationale=rationale)
    return plan.model_dump_json()


PLAN_TOOL = StructuredTool.from_function(
    func=submit_execution_plan,
    name="submit_execution_plan",
    description=(
        "Submit exactly one validated execution plan. Each task must contain task_id, "
        "agent (knowledge-agent, tool-agent, or web-agent), query, optional depends_on, "
        "parallel_group, and constraints."
    ),
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


def create_execution_planner() -> _PlannerAgent:
    """Create a fresh planner instance for one workflow invocation."""
    logger.info("agent.create supervisor-planner model=deepagent")
    return _PlannerAgent()


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
    """Extract the JSON returned by the executed submit_execution_plan tool."""
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


def _normalize_plan(value: dict[str, Any]) -> ExecutionPlan:
    """Validate and canonicalize a plan before comparing representations."""
    return ExecutionPlan.model_validate(value)


def extract_execution_plan(result: Any) -> ExecutionPlan:
    """Extract the validated plan from DeepAgents/LangChain tool-call messages.

    LangGraph/DeepAgents can expose the same StructuredTool execution through both
    the AI tool-call message and the resulting ToolMessage. Those two representations
    are not necessarily byte-for-byte identical: omitted Pydantic defaults may appear
    in the executed tool result. Compare canonical ExecutionPlan models instead of
    raw dictionaries, so representation differences are not mistaken for two plans.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    submitted: list[ExecutionPlan] = []

    for message in messages:
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls", [])
        else:
            tool_calls = getattr(message, "tool_calls", [])
        for call in tool_calls or []:
            name = _message_value(call, "name")
            if name == "submit_execution_plan":
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
            len(submitted),
            [plan.model_dump(mode="json") for plan in submitted],
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

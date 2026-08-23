from __future__ import annotations

import json
import logging
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from langchain_core.tools import StructuredTool

from app.agents.execution_plan import ExecutionPlan, ExecutionPlanInput
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
interface. Its schema is strict. Use ONLY these agent values: knowledge-agent,
tool-agent, web-agent. NEVER emit aliases such as knowledge, knowledge_agent, tool,
tool_agent, web, web_agent, general-purpose, or general-purpose-agent.
For optional fields, prefer omitting them rather than emitting null.
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


def submit_execution_plan(
    tasks: list[dict[str, Any]], rationale: str | None = None
) -> str:
    """Function-calling entry point with the strict canonical plan schema."""
    payload = ExecutionPlanInput(tasks=tasks, rationale=rationale)
    plan = payload.to_execution_plan()
    return plan.model_dump_json()


PLAN_TOOL = StructuredTool.from_function(
    func=submit_execution_plan,
    name="submit_execution_plan",
    description=(
        "Submit exactly one validated execution plan. Each task MUST use one of "
        "the exact agent values knowledge-agent, tool-agent, or web-agent."
    ),
    args_schema=ExecutionPlanInput,
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
    """Validate a tool call without rewriting the Supervisor's agent selection."""
    return dict(value)


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

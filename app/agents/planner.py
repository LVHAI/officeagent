from __future__ import annotations

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
    logger.info("agent.create supervisor-planner model=deepagent")
    return _PlannerAgent()


def extract_execution_plan(result: Any) -> ExecutionPlan:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    calls: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls", [])
        else:
            tool_calls = getattr(message, "tool_calls", [])
        for call in tool_calls or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name == "submit_execution_plan":
                calls.append(call)
    if len(calls) != 1:
        raise ValueError(
            f"Supervisor must call submit_execution_plan exactly once; got {len(calls)}"
        )
    if isinstance(calls[0], dict):
        args = calls[0].get("args", {})
    else:
        args = getattr(calls[0], "args", {})
    return ExecutionPlan.model_validate(args)

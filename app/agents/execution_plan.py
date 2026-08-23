from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AgentKind = Literal["knowledge-agent", "tool-agent", "web-agent"]


class ExecutionTask(BaseModel):
    """A single unit of work that LangGraph is responsible for executing."""

    task_id: str = Field(min_length=1)
    agent: AgentKind
    query: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    parallel_group: str = "default"
    constraints: dict[str, object] = Field(default_factory=dict)

    @field_validator("depends_on", mode="before")
    @classmethod
    def normalize_nullable_depends_on(cls, value: Any) -> Any:
        return [] if value is None else value

    @field_validator("parallel_group", mode="before")
    @classmethod
    def normalize_nullable_parallel_group(cls, value: Any) -> Any:
        return "default" if value is None or value == "" else value

    @field_validator("constraints", mode="before")
    @classmethod
    def normalize_nullable_constraints(cls, value: Any) -> Any:
        return {} if value is None else value


class ExecutionPlan(BaseModel):
    """Validated Supervisor output consumed by the LangGraph orchestrator."""

    tasks: list[ExecutionTask] = Field(min_length=1, max_length=12)
    rationale: str = ""

    @field_validator("rationale", mode="before")
    @classmethod
    def normalize_nullable_rationale(cls, value: Any) -> Any:
        return "" if value is None else value

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionPlan":
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("execution plan contains duplicate task_id")
        known = set(ids)
        for task in self.tasks:
            if task.task_id in task.depends_on:
                raise ValueError(f"task {task.task_id} cannot depend on itself")
            unknown = set(task.depends_on) - known
            if unknown:
                raise ValueError(
                    f"task {task.task_id} depends on unknown tasks: {sorted(unknown)}"
                )
        return self


class ExecutionTaskInput(BaseModel):
    """Function-calling input schema: LLMs sometimes emit explicit null defaults."""

    task_id: str = Field(min_length=1)
    agent: AgentKind
    query: str = Field(min_length=1)
    depends_on: list[str] | None = None
    parallel_group: str | None = None
    constraints: dict[str, object] | None = None


class ExecutionPlanInput(BaseModel):
    """Strict structured-output contract exposed to the planner function call."""

    tasks: list[ExecutionTaskInput] = Field(min_length=1, max_length=12)
    rationale: str | None = None

    def to_execution_plan(self) -> ExecutionPlan:
        return ExecutionPlan.model_validate(self.model_dump())


def plan_from_tool_result(value: object) -> ExecutionPlan:
    """Normalize StructuredTool/Pydantic/dict results into an ExecutionPlan."""
    if isinstance(value, ExecutionPlan):
        return value
    if isinstance(value, dict):
        return ExecutionPlan.model_validate(value)
    raise TypeError(f"unsupported execution plan value: {type(value).__name__}")

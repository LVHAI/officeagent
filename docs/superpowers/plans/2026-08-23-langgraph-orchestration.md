# LangGraph Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LangGraph the real workflow/state/parallel orchestration layer while keeping DeepAgents as the Supervisor and Tool Agent runtimes.

**Architecture:** Supervisor creates an explicit execution plan without executing child work. LangGraph expands the selected Knowledge/Tool/Web tasks into parallel branches, stores normalized AgentOutput values in State, aggregates results, and can re-plan failed/insufficient work before Report.

**Tech Stack:** Python 3.12, LangGraph, DeepAgents, LangChain, FastAPI, Milvus, MCP, Tavily, PostgreSQL checkpointer.

**Spec:** `docs/spec.md` and `docs/plan.md`

## Global Constraints

- Knowledge Agent uses the direct RAG pipeline and never MCP/Web.
- Tool Agent uses Skill → MCP dynamic discovery and never receives the global MCP registry.
- Web Agent uses Tavily only when current/external evidence is required.
- Supervisor does not receive concrete MCP tool schemas.
- LangGraph owns workflow state, persistence, parallel execution, retry/timeout boundaries, and recovery.
- Partial results are preserved; missing evidence must never be fabricated.

---

### Task 1: Explicit execution plan contract

**Files:**
- Create: `app/agents/execution_plan.py`
- Modify: `app/agents/deepagents.py`
- Test: `tests/agents/test_execution_plan.py`

- [ ] Add a normalized `ExecutionTask` / `ExecutionPlan` contract with task id, agent type, query, dependencies, parallel group, and constraints.
- [ ] Add a Supervisor planning tool that returns the validated plan.
- [ ] Remove child subagents from the Supervisor runtime so Supervisor planning cannot execute Knowledge/Tool/Web directly.
- [ ] Keep Supervisor prompt explicit about routing rules and minimum required agents.
- [ ] Test plan validation, duplicate tasks, unsupported agents, and dependency ordering.

### Task 2: LangGraph dynamic fan-out

**Files:**
- Modify: `app/agents/graph.py`
- Test: `tests/agents/test_dynamic_fanout.py`

- [ ] Parse the Supervisor plan into graph execution tasks.
- [ ] Execute independent tasks concurrently with bounded concurrency.
- [ ] Route each task to exactly one specialized runtime.
- [ ] Persist each AgentOutput in State.
- [ ] Preserve task/delegation/traces on success, timeout, cancellation, and failure.
- [ ] Test Knowledge+Tool+Web parallel execution and single-agent routing.

### Task 3: Result aggregation

**Files:**
- Create: `app/agents/aggregator.py`
- Modify: `app/agents/graph.py`
- Test: `tests/agents/test_result_aggregator.py`

- [ ] Normalize outputs into facts, sources, errors, and partial-result markers.
- [ ] Deduplicate identical sources.
- [ ] Keep failed agent evidence separate from successful evidence.
- [ ] Produce a stable report context for Report Agent.

### Task 4: Supervisor re-planning

**Files:**
- Modify: `app/agents/deepagents.py`
- Modify: `app/agents/graph.py`
- Test: `tests/agents/test_replanning.py`

- [ ] Allow Supervisor to receive prior AgentOutput summaries.
- [ ] Request a second plan only when a task failed or the result explicitly indicates missing evidence.
- [ ] Limit re-planning to one round.
- [ ] Do not treat transport retry as re-planning.
- [ ] Preserve both original and re-planned delegation traces.

### Task 5: Acceptance and regression coverage

**Files:**
- Modify/Create: `tests/agents/test_graph_acceptance.py`
- Test: existing routing/skill/RAG/web tests

- [ ] Verify recipe/knowledge questions never invoke Tool/Web.
- [ ] Verify enterprise customer queries invoke Tool → Skill → MCP only.
- [ ] Verify current/external questions invoke Web → Tavily.
- [ ] Verify mixed SQL + Web tasks fan out concurrently.
- [ ] Verify a failed branch does not discard successful branches.
- [ ] Run the complete test suite and static checks before commit.

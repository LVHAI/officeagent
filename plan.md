# RAG Chunking Document Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organize source documents for the four existing RAG chunking strategies into dedicated folders, make folder selection explicit and deterministic, and keep the RAG ingestion pipeline compatible with the existing `DocumentChunk` and retrieval flow.

**Architecture:** The document corpus will be divided into `policy`, `faq`, `parent_child`, and `semantic` directories. The loader will use the first directory below the configured corpus root as the explicit chunking strategy, validate that the strategy is supported, and retain content-based classification only as a backward-compatible fallback for individual files outside strategy folders. The selected strategy will be persisted in document metadata so downstream chunking, indexing, debugging, and retrieval can distinguish the four routes.

**Tech Stack:** Python 3.12, pathlib, Pydantic models already used by `app.rag`, pytest.

**Spec:** Existing RAG implementation in `app/rag/loader.py`, `app/rag/splitter.py`, `app/rag/parent_child.py`, and `app/rag/pipeline.py`.

## Global Constraints

- Preserve the existing four strategy names exactly: `policy`, `faq`, `parent_child`, `semantic`.
- Do not change the retrieval contract in `RetrievalPipeline`.
- Do not silently reinterpret an explicitly named strategy folder.
- Unsupported strategy folders must fail with a clear error.
- Keep content-based classification as a compatibility fallback for files not placed under a strategy directory.
- Document metadata must contain the selected `doc_type` for downstream indexing and debugging.
- Use TDD: write failing tests before implementation changes.

---

### Task 1: Define the strategy-folder contract and corpus layout

**Files:**
- Create: `data/rag/policy/.gitkeep`
- Create: `data/rag/faq/.gitkeep`
- Create: `data/rag/parent_child/.gitkeep`
- Create: `data/rag/semantic/.gitkeep`
- Modify: `plan.md`

**Interfaces:**
- Corpus root: `data/rag/`
- Strategy folders: `policy`, `faq`, `parent_child`, `semantic`
- Each strategy folder accepts the currently supported `.txt` and `.md` source documents.

- [ ] **Step 1:** Add the four empty strategy directories with `.gitkeep` files so the expected corpus structure is visible in Git.
- [ ] **Step 2:** Document example filenames and the meaning of each strategy directory in `README.md` or the RAG documentation if a suitable existing document exists.
- [ ] **Step 3:** Verify the repository contains all four directories.
- [ ] **Step 4:** Commit: `docs: define rag chunking strategy folders`

---

### Task 2: Add tests for explicit strategy-folder classification

**Files:**
- Modify/Create: `tests/rag/test_loader.py`

**Interfaces:**
- `DocumentLoader.load(path)` continues to return document text.
- Add a strategy-aware API, preferably `DocumentLoader.resolve_type(path, corpus_root=...) -> str`, without breaking `DocumentTypeClassifier.classify(...)`.

- [ ] **Step 1:** Write a test proving `data/rag/policy/example.md` resolves to `policy` even when its content does not contain policy markers.
- [ ] **Step 2:** Write equivalent tests for `faq`, `parent_child`, and `semantic`.
- [ ] **Step 3:** Write a test proving a file directly under the corpus root uses the existing content-based classifier as a fallback.
- [ ] **Step 4:** Write a test proving an unsupported first-level strategy folder raises a clear `ValueError`.
- [ ] **Step 5:** Run `pytest tests/rag/test_loader.py -v` and confirm the new tests fail before implementation.

---

### Task 3: Implement deterministic folder-based strategy resolution

**Files:**
- Modify: `app/rag/loader.py`

**Interfaces:**
- Preserve `DocumentLoader.load(path) -> str`.
- Add a strategy resolver that accepts a file path and optional corpus root and returns one of the four supported strategy names.
- Explicit strategy folders have precedence over content classification.
- Paths outside a configured strategy-folder corpus retain the current classifier fallback.

- [ ] **Step 1:** Add a constant for the four supported strategies.
- [ ] **Step 2:** Implement path-based strategy resolution using `pathlib.Path` and a corpus root.
- [ ] **Step 3:** Validate explicit folder names and raise a descriptive error for unsupported names.
- [ ] **Step 4:** Keep the existing content classifier unchanged for backward compatibility.
- [ ] **Step 5:** Run `pytest tests/rag/test_loader.py -v` and confirm all loader tests pass.
- [ ] **Step 6:** Commit: `feat: resolve rag chunking strategy from document folders`

---

### Task 4: Propagate the selected strategy into ingestion/chunk metadata

**Files:**
- Modify: `app/rag/splitter.py`
- Modify: `app/rag/parent_child.py` if required by the existing ingestion contract
- Modify: relevant ingestion/indexing module discovered during implementation
- Test: `tests/rag/test_chunk_metadata.py`

**Interfaces:**
- Every generated `DocumentChunk` must carry `doc_type` equal to the resolved strategy.
- Existing policy article metadata and parent-child relationships must remain intact.

- [ ] **Step 1:** Write failing tests asserting `doc_type` survives chunk creation for all four strategies.
- [ ] **Step 2:** Update chunk creation to preserve the resolved strategy in metadata.
- [ ] **Step 3:** Ensure `policy` keeps `article` metadata and `parent_child` keeps `parent_id` metadata.
- [ ] **Step 4:** Run the focused RAG tests.
- [ ] **Step 5:** Commit: `feat: preserve rag chunking strategy metadata`

---

### Task 5: Verify end-to-end RAG compatibility

**Files:**
- Test: existing RAG tests plus a new integration test under `tests/rag/` if needed

**Interfaces:**
- `RetrievalPipeline.retrieve_async()` and `retrieve()` signatures remain unchanged.
- Strategy metadata can be used by existing `metadata_filter` without changing retrieval behavior.

- [ ] **Step 1:** Add one representative document fixture to each strategy folder.
- [ ] **Step 2:** Run all RAG tests.
- [ ] **Step 3:** Run the full test suite with `pytest -q`.
- [ ] **Step 4:** Verify no existing retrieval behavior regresses.
- [ ] **Step 5:** Commit: `test: verify rag strategy folder ingestion`

---

### Task 6: Documentation and final verification

**Files:**
- Modify: `README.md` or the most appropriate existing RAG documentation
- Modify: `plan.md` to mark completed steps

- [ ] **Step 1:** Document the directory structure:
  - `data/rag/policy/`
  - `data/rag/faq/`
  - `data/rag/parent_child/`
  - `data/rag/semantic/`
- [ ] **Step 2:** Document that the directory name is the explicit chunking strategy and content classification is only the fallback.
- [ ] **Step 3:** Run `pytest -q`.
- [ ] **Step 4:** Review the final diff for accidental changes to retrieval APIs.
- [ ] **Step 5:** Commit: `docs: document rag chunking corpus layout`

---

## Expected Result

The corpus will be visually and operationally separated:

```text
 data/rag/
 ├── policy/          # policy_nodes / article-level chunks
 ├── faq/             # FAQ-oriented chunks
 ├── parent_child/    # parent-child chunks
 └── semantic/        # semantic/baseline chunks
```

A document's location determines its intended chunking strategy, and the selected strategy is carried into chunk metadata. This makes ingestion easier to inspect, test, and extend without coupling retrieval logic to filesystem conventions.

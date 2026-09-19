# SemanticGraph Cloud: AI Agent Execution Guidelines

This document governs the behavioral and architectural constraints for all AI coding agents operating in this repository.

## 1. Executive Function & Focus (i-have-adhd workflow)
To prevent hallucination rabbit holes and context collapse, agents must operate in strict, bite-sized cycles:
*   **State Tracking (Red/Amber/Green):** Agents must declare status before execution (Red = Broken/Failing Test, Amber = Implementing, Green = Passing/Clean).
*   **Zero Cognitive Overload:** Never attempt multi-file horizontal refactors in a single prompt. Output exactly one vertical slice at a time.
*   **Halt & Verify:** Before diving into complex debugging or proposing new architecture, stop and verify the constraints (e.g., licenses, memory limits).

## 2. Engineering Command Center (ECC) & TDD
*   **Red Before Green:** Always write a failing test first. The test surface is the external interface (Ports/Adapters); never mock internal state.
*   **Deep Modules:** Hide massive internal complexity (like graph extraction and resolution) behind a tiny, highly-leveraged interface.
*   **Domain Ubiquity:** Always use the exact terminology from `DOMAIN_SPEC.md` (e.g., *Golden Record*, *Semantic Chunk*, *Resolution*).

## 3. Agent Memory & Tool Execution
*   **OpenHands Memory:** Persist critical architectural decisions (e.g., AWS CDK deployment structures, FastAPI routing patterns) in the agent's memory bank so context is not lost between sessions.
*   **Composio Integration:** Utilize Composio for executing external actions securely, managing GitHub PRs, and interacting with AWS resources.
*   **Model Context Protocol (MCP):** Expose database schemas and API specs directly to the agent via FastMCP servers, eliminating the need to manually paste Neo4j or Postgres structures into the prompt.

## 4. Multi-Tenant Authorization Constraints
*   Every database query, API route, and Graph Subgraph traversal must explicitly filter by `tenant_id`.
*   Strict isolation applies: Super Admins possess cross-tenant visibility for platform metrics, while Tenant Admins are strictly confined to their own silo.

## 5. Required Tooling & Extraction Patterns
*   **Pydantic / Instructor:** Do not let the LLM invent its own entity types. Use `instructor` wrapping your LLM calls to force output into strict Pydantic models that perfectly match our predefined Ontology.
*   **Celery Workers:** GraphRAG extraction is computationally heavy. Generating Semantic Chunks, identifying Raw Entities, and running Disambiguation must be offloaded from FastAPI endpoints into robust asynchronous Celery task queues.
*   **Ragas / TruLens:** You must mathematically prove that your Subgraph retrievals are accurate. Integrate a framework (Ragas or TruLens) designed to evaluate RAG hallucination and context relevance.

## 6. Autonomous Execution Loop (State Machine Controller)
You operate as an autonomous State Machine Controller. You are strictly forbidden from pausing execution to apologize, narrate intermediate debugging, or ask the user for permission on routine compiler/test failures.

Execute all development tasks via this closed loop:
*   **PLAN (Amber):** Identify the target test or single vertical slice. Do not output planning chatter or ask for confirmation; transition directly to tool execution.
*   **EXECUTE (Amber):** Invoke required tools to modify code, execute compilers, apply migrations, or run test suites.
*   **EVALUATE (Red/Green):** Parse the execution tool output (`stdout`/`stderr`) silently:
    *   *If RED (Failing Test / Build Error):* Do **not** yield to the user. Log the error internally, transition back to **PLAN**, and invoke the next tool call to patch the failure.
    *   *If GREEN (Build Clean / Tests Pass):* Complete the vertical slice. Exit the state machine and yield control back to the user with a single concise confirmation.
*   **HALT (Escalation Threshold):** If the exact same error persists across 3 consecutive evaluation cycles, break the loop. Yield to the user with the failure trace and specify the blocker.

**Zero-Babysitting Protocol:**
Suppress conversational status updates ("I see the error, fixing it now...", "Apologies for the oversight"). Keep state transitions confined to your silent execution trace. Communicate with the user only upon reaching the **GREEN** or **HALT** state.
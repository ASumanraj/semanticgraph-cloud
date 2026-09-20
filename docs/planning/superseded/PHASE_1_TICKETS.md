# Phase 1: Core Foundation & Multi-Tenant Silo

This document tracks the tickets and parallel execution plan for Phase 1 of SemanticGraph Cloud.

## Ticket 1: Backend Foundation (FastAPI & SQLModel)
**Assignee**: Backend Architect Subagent
**Path**: `S:\semanticgraph-cloud\backend`
**Required Skill**: `fastapi`
**Objectives**:
1. Initialize the Python environment using `uv`.
2. Set up the FastAPI application entrypoint (`fastapi dev` / `fastapi run`).
3. Define the core multi-tenant Postgres schemas using SQLModel (`Tenant` and `Ontology`).
4. Implement the `tenant_id` dependency injection (`Annotated[..., Depends(...)]`) to strictly enforce tenant boundaries on all routes.
5. Adhere to Red/Amber/Green TDD states.

## Ticket 2: Frontend Prototype (Modern Web UI)
**Assignee**: Frontend Prototyper Subagent
**Path**: `S:\semanticgraph-cloud\frontend`
**Required Skill**: `modern-web-guidance`
**Objectives**:
1. Research and build a highly performant, standard UI prototype for the Tenant Dashboard.
2. The UI must include views for defining the **Ontology** and uploading **Documents**.
3. Utilize modern web features (e.g., View Transitions, modern CSS layouts) without bloating with unnecessary legacy frameworks.

## Ticket 3: Infrastructure Scaffold (AWS CDK)
**Assignee**: Infrastructure Engineer Subagent
**Path**: `S:\semanticgraph-cloud\infra`
**Required Skill**: `aws-cdk`
**Objectives**:
1. Initialize a new AWS CDK project.
2. Scaffold the fundamental L2 constructs required for Phase 1 and 2: A VPC and an Amazon RDS PostgreSQL instance.
3. Ensure the construct IDs are stable and `cdk synth` compiles perfectly (Red/Amber/Green).

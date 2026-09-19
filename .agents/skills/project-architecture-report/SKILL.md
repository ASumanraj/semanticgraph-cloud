---
name: project-architecture-report
description: "Creates a standalone HTML report that maps a codebase: structure, flows, dependencies, data model, symbols, risks, gaps, and likely next needs. Use when the user asks for architecture analysis, dependency or flow mapping, an HTML project report, or scripts/sub-agents to list files, functions, classes, and interfaces."
disable-model-invocation: true
---

# Project Architecture Report

Analyze the project and produce a useful HTML file. The report should help someone quickly understand what exists, how it works, what hurts, and what the codebase likely needs next.

## Quick Start

Run the bundled inventory script, then turn findings into a standalone HTML report:

```bash
node scripts/project-inventory.mjs --root /path/to/project --out .scratch/project-inventory.json
```

Default report path: `.scratch/project-architecture-report.html`.

## Workflow

1. Define scope and report path. If none given, inspect current repo and write `.scratch/project-architecture-report.html`.
2. Read local truth: `AGENTS.md`, `CLAUDE.md`, `README.md`, `CONTEXT.md`, ADRs, manifests, env examples, CI, tests, deploy config, docs, and ticket/PRD artifacts.
3. Run `project-inventory.mjs`. Add project-native maps when available: route list, DB schema, OpenAPI/GraphQL schema, migration history, package graph, test graph, build graph, and generated clients.
4. When useful, split broad analysis into independent sub-agent questions: structure/deps, runtime flows, data/storage, UI/API surfaces, tests/tooling, and risk/gap detection. Parent agent owns final report and resolves conflicts.
5. Trace flows from entrypoints to state and side effects: user flows, request flows, background jobs, CLI commands, auth/session paths, storage writes, external APIs, and error paths.
6. Identify dependencies: runtime, dev/build, internal packages, generated code, external services, browser/runtime assumptions, env vars, and hidden operational coupling.
7. Extract data model: persisted entities, in-memory state, files, caches, queues, events, schemas, migrations, validation rules, ownership, and lifecycle.
8. Write HTML with no external dependency unless user permits it. Include CSS, a table of contents, scannable cards/tables, code-path links as plain paths, diagrams as inline Mermaid source or simple HTML/CSS flow blocks, and next-need recommendations.
9. Verify: report file exists, opens locally, has no broken local asset refs, and contains exact sections below.

## Required HTML Sections

- Overview: project purpose, current shape, likely needs
- Architecture map: packages, apps, entrypoints, modules, ownership
- Runtime flows: main user/request/job/CLI flows
- Data model: entities, state, persistence, schemas, lifecycle
- Dependencies: package deps, external services, tools, env vars
- Code inventory: files, symbols, routes, tests, scripts, generated paths
- Pain points: duplication, shallow modules, legacy, missing tests, risky coupling
- Needs map: keep/change/delete, improvement slices, open questions
- Appendix: commands run, generated inventory path, assumptions, gaps

## Style

Be brief but complete. Prefer exact paths, tables, and flow steps over prose. Mark uncertainty as `Needs evidence`.

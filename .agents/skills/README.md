# Skills

Skills `agy` and other agent runners load from this workspace. Two provenances:

**Installed via `skills-lock.json`** — pinned by source and content hash:
`agent-memory`, `aws-cdk`, `brainstorming-research-ideas`, `composio`,
`deep-research`, `fastapi`, `i-have-adhd`, `project-architecture-report`,
`wf-planning-solution-architect`.

**Vendored from ECC** (github.com/affaan-m/ECC at `dd6ee53`), copied because they
bear directly on the work in `docs/architecture/ENTERPRISE_PLAN.md`:

| Skill | Used for |
|---|---|
| `tdd-workflow` | Red-green-refactor, the rhythm AGENTS.md requires |
| `e2e-testing` | Playwright: page objects, fixtures, CI artifacts, flake control |
| `backend-patterns` | API structure, database access, server-side conventions |
| `frontend-patterns` | React and Next.js structure, state, performance |
| `api-design` | REST resource naming, status codes, pagination, error shape |
| `nextjs-turbopack` | Next 16 / Turbopack build and dev-server behaviour |

These are copies, not lockfile entries: `skills-lock.json` is written by the CLI
that installed the first group, with a `computedHash` whose scheme is not
reproducible here, and a guessed hash is worse than an honest note. To refresh
one, re-copy it from an ECC checkout at the commit above.

ECC itself lives outside this repo — it is a 3,700-file library whose own
`.agents/`, `.claude/` and `.codex/` trees would otherwise compete with this
directory for skill discovery.

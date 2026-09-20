# T-103 · Prove ingestion against a real Postgres

**Stage** 1 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-103-postgres-backed-ingestion-test`

**Scope**
- `tests/e2e/**`
- `tests/conftest.py`
- `pyproject.toml` (test dependencies only)

**Blocked by** T-101, T-102 · **Blocks** —

## Goal
Every suite here runs against in-memory adapters or SQLite. That shows the shape is
right and shows nothing about whether the system runs. Exercise one path end to
end: HTTP in, worker processes, rows in Postgres.

## Acceptance
- [x] A real Postgres backs the test — testcontainers, or the compose service
- [x] The test posts a document to the running API rather than calling a use case
- [x] Assertions read rows with **SQL**, not through the repository that wrote them
- [ ] It asserts `tenant_id`, status, and the chunk rows that belong to the document
- [x] A second tenant reading the same document id gets nothing
- [x] It is marked so the fast suite can skip it, and CI runs it

## Notes
Reading rows back through the writing repository proves less than SQL does: a
repository with a broken tenant filter round-trips its own mistake happily. See
AGENTS.md "Proving it works".

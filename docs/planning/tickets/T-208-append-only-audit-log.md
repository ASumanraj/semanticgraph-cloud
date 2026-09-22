# T-208 · Append-only audit log

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-208-append-only-audit-log`

**Scope**
- `alembic/**`
- `src/semanticgraph/control/audit/**`
- `tests/integration/control/**`

**Blocked by** T-207 · **Blocks** —

## Goal
Record authentication, authorization failures, admin changes, data access, export,
deletion, API-key lifecycle and **every LLM invocation** — tenant, user, model,
version, token counts, scope. It is also the debugging surface and the billing
substrate, so it pays for itself three times.

## Acceptance
- [x] The application role has no UPDATE or DELETE grant on the audit table
- [x] Every listed event type is captured
- [x] LLM invocations record model and version alongside token counts
- [x] Retention is 15 months, covering a SOC 2 Type II window plus buffer
- [x] Entries are exportable per tenant
- [x] **No document text is stored** — ids and hashes only

## Notes
Content in the audit log inherits the same erasure obligations as the primary store,
which is why it holds references rather than text. An auditor also asks for evidence
that someone reviews it: logs nobody reads are not a control.

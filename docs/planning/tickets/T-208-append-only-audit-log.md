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
- [ ] Retention is 15 months, covering a SOC 2 Type II window plus buffer — the *mechanism* used to enforce append-only-ness (see Review) makes this reliant on a convention rather than a database guarantee, so re-verify once the fix below lands
- [x] Entries are exportable per tenant
- [x] **No document text is stored** — ids and hashes only

## Notes
Content in the audit log inherits the same erasure obligations as the primary store,
which is why it holds references rather than text. An auditor also asks for evidence
that someone reviews it: logs nobody reads are not a control.

## Review

Reviewed 2026-09-22 against `main` at `699816a`. 365 tests pass, e2e passes, lint and format
clean. The schema, indexes (`tenant_id` leading), FORCE RLS, and the `GRANT SELECT, INSERT`-only
grant are all real and correctly built.

**Reopened for one defect, reproduced against the real dev database:**

The immutability trigger's own escape hatch is bypassable by the exact role it's supposed to
constrain. `prevent_audit_event_mutation()` allows a DELETE whenever
`current_setting('app.allow_retention_prune', true) = 'true'` — but nothing checks *who* set that
value. PostgreSQL lets any role set an arbitrary custom GUC on its own connection by default, so
`semanticgraph_app` — the same role every ordinary request uses — can simply run
`SET LOCAL app.allow_retention_prune = 'true'` on its own connection and then delete any row it
likes. Verified directly against the dev database:

```
plain delete refused: Audit event log is append-only. Deletions are prohibited.
SELF-SET PRUNE DELETE SUCCEEDED -- BAD: app role bypassed immutability using its own GUC
rows remaining: 0
```

`AuditLog.prune_expired_events()`'s docstring says it "requires administrative privileges (an
admin_session)," but the parameter is typed as a plain `AsyncSession` with no check that the
connection is anything other than the ordinary `semanticgraph_app` role — because no other role
was ever created. There is no technical difference between an "admin session" and any other
session; the guarantee is a comment, not a grant.

This defeats the ticket's whole point. An audit log whose deletions are stopped only by "nothing
in our own code happens to call `SET LOCAL app.allow_retention_prune`" is not append-only against
a bug elsewhere in the app, and it is not append-only against anyone with database credentials —
which, since there's only one non-superuser role, is the same credentials every request already
uses.

**Fix direction:** privilege must be checked by role identity, not by a value the same role can
set. A real second Postgres role (e.g. `semanticgraph_retention`) that alone is granted a way to
delete — either a table-level DELETE grant it alone holds, or a `SECURITY DEFINER` function it
alone may call — and the trigger checks `current_user` (or the function checks its own caller),
not a self-settable GUC. `prune_expired_events` then genuinely requires a different set of
credentials to run, which is what "requires administrative privileges" should mean.

Continue on a new branch off `main`. Add a test that connects as `semanticgraph_app` and asserts
that setting the escape-hatch GUC itself and then deleting is refused — the case the current test
suite has no coverage for at all.

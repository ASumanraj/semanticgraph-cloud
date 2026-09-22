# T-209 · OpenTelemetry with tenant attribution

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-209-otel-tenant-attribution`

**Scope**
- `src/semanticgraph/observability/**`
- `src/semanticgraph/composition/container.py`
- `src/semanticgraph/adapters/inbound/**`
- `tests/unit/observability/**`

**Blocked by** — · **Blocks** —

## Goal
`tenant_id` on every span, metric and log line, propagated explicitly through worker
headers — it does not cross the broker on its own, and that is the usual gap.
Retrofitting tenant attribution across an existing trace surface is miserable, and
it always happens under deadline pressure from a billing dispute.

Runs in parallel with the migration chain: no Alembic revision, disjoint paths.

## Acceptance
- [x] `tenant_id` is a resource or span attribute on every span, metric and log line
- [x] Tenant context crosses the worker boundary explicitly
- [x] The stable `gen_ai.*` core is instrumented: operation, provider, model, input and output tokens
- [ ] **Document text never reaches telemetry** — ids and hashes only. **Not true as built; see Review**
- [ ] A lint or review rule enforces that, before the codebase has 200 log statements — the rule exists but does not cover the case that matters most (see Review)

## Notes
These attributes are also the cost-attribution substrate: cloud billing cannot
attribute model tokens to a tenant, and AWS Application Cost Profiler is
discontinued. Only this instrumentation can.

## Review

Reviewed 2026-09-22 against `main` at `699816a`. Tenant attribution on spans/metrics/logs, the
worker-boundary propagation, and the `gen_ai.*` core instrumentation all check out.

**Reopened for one defect, reproduced directly:**

Both hygiene checks — the static AST linter (`observability/lint.py`) and the runtime guard
(`observability/logging.py`'s `assert_telemetry_hygiene`) — only ever inspect **structured
fields**: the AST linter checks the `extra={...}` dict and hard-coded attribute/variable names;
the runtime guard checks only `kwargs["extra"]`. **Neither ever looks at the primary log
message** — the single most natural way anyone actually writes a log line. Two ways to trigger it,
both verified:

```python
# 1. A renamed local variable defeats the static linter completely — zero violations reported:
content = chunk.text
logger.info(content)  # lint_source_string() returns []
logger.info(f"processing: {content}")  # also []

# 2. The runtime guard never fires on the primary message at all:
logger.info(long_document_text)   # no exception, and it lands verbatim in the JSON log line
```

`chunk.text` passed directly (`logger.info(chunk.text)`) *is* caught by the static linter — that
narrow case works. But renaming the variable to anything not in the linter's four-word
`FORBIDDEN_IDENTIFIERS` set, or building an f-string from that renamed variable, defeats it
silently, and the runtime guard provides no backstop because it was never wired to check `msg` at
all — only `extra`. This is exactly the AGENTS.md rule this ticket exists to satisfy
("Document text stays out of logs, traces, and span attributes") and exactly the failure mode
named there (a GDPR-disclosed retention exposure), and it fails on the most ordinary possible
code, not an adversarial one.

**Fix direction:** the runtime guard has to run on `record.getMessage()` (the rendered message,
after `%`-formatting/f-string interpolation) for every record, not only on `extra`, most naturally
inside `TenantLogFilter.filter()` where `record.message` is currently in the *exclude* list.
Length-based heuristics (already present via `MAX_SAFE_ATTR_LENGTH`) are a reasonable backstop for
the message body too, since a 500+ character string as a log message is never legitimate content
regardless of what variable held it. The static linter is defense in depth and can stay narrow;
the runtime guard cannot skip the one field almost every log call actually uses.

Continue on a new branch off `main`. Add a test that calls `logger.info()` with a long string via
a renamed local variable (not a keyword named `document_text`) and asserts it raises or is
redacted — the case the current test suite has no coverage for at all.

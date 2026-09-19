# ADR-0003: Temporal for the document pipeline, not Celery

## Status
**Accepted** — 2026-09-20. Celery remains in `pyproject.toml` as transitional until Stage 3 lands.

## Deciders
- Platform Team

## Context

`AGENTS.md` and `ARCHITECTURE.md` mandated Celery for ingestion, and
`adapters/inbound/workers/` implements it. Celery is a good task queue. The document pipeline is
not a set of tasks — it is a long-running, branchy, expensive, human-interruptible **workflow**,
and the mismatch has specific consequences:

- **At-least-once delivery plus a visibility timeout produces duplicate paid LLM calls.** A
  5-minute extraction under a 3-minute visibility timeout is executed twice by two workers. The
  usual advice is to set the timeout above the longest task, but the longest task here is
  *unbounded* — a 500-page document with gleaning — so no correct value exists. Set it high and
  crash recovery takes that long; set it low and the customer's extraction is billed twice.
- **`countdown`/`eta` beyond the visibility timeout produces duplicates that look like application
  bugs.** This surfaces the first time LLM rate-limit backoff is implemented.
- **There is no durable workflow state.** A worker dying at step 7 of 9 leaves no record of steps
  1–6, so the pipeline re-runs and re-pays for every LLM call already bought. At $0.07–1.49 per
  document that is a P&L line, not an inconvenience.
- **Redis is single-threaded.** Every push, pop, ack and visibility-timeout check runs on one core
  and becomes the bottleneck before the workers do.
- **Observability is task-shaped.** "Task X failed" is visible; "document 4,712 is stuck at
  resolution, having completed extraction, at $3.40 so far" is not.

The product also requires a human-in-the-loop entity-resolution review queue
([ADR-0002](0002-postgres-as-the-graph-store.md) context; ENTERPRISE_PLAN Part 2.2), which means a
workflow that pauses indefinitely and resumes on a human decision.

## Decision

**Temporal Cloud runs the document pipeline.** Activities are the expensive, retryable units —
parse, chunk, contextualize, extract, resolve, materialize — which is the granularity the existing
Celery task bodies already have. Review-queue pauses use Temporal Signals.

Celery is retained only for short, idempotent, fire-and-forget side work (email, webhooks, cache
warming), or dropped entirely.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **Stay on Celery** | Every month adds pipeline logic entangled with `chain`/`chord`/`group` semantics that have no equivalent in a durable-execution engine. Migrate at 6 steps, not 30 |
| **AWS Step Functions** | **256 KiB maximum input/output per state** is disqualifying — every chunk list and candidate-pair batch exceeds it, so each transition becomes an S3 write plus a pointer. The **25,000-event execution-history cap** then bites on per-chunk fan-out. Express workflows dodge the history cap but stop at **5 minutes** |
| **Prefect / Dagster** | Batch-DAG tools over assets. Dagster's asset lineage is attractive for re-indexing, but the wrong shape for per-document, long-running, human-interruptible ingestion |
| **Ray** | A compute framework, not an orchestrator. Correct *inside* an activity for GPU fan-out (GLiNER, embeddings); not a replacement for one |
| **Self-hosted Temporal** | Only cost-competitive around 30–50M actions/month for a team already running Kubernetes and Cassandra. Below that, Cloud is cheaper once operational labour is priced |

## Consequences

**Accepted costs.** Temporal has a real learning curve — roughly two weeks. Workflow code must be
deterministic: no `datetime.now()`, no `random`, no direct I/O, all of which move into activities.
**Workflow versioning must be handled from the first deploy** or in-flight executions break.

Temporal Cloud pricing is $50/M actions, falling to $25/M at volume, with no minimum. Confirm the
bill at projected volume before committing (ENTERPRISE_PLAN Part 8, open question 3).

**Migration shape.** Wrap each existing Celery task body as a Temporal activity, write the workflow
that sequences them, run both in parallel, and cut over per tenant.

## References
- [`docs/architecture/ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Part 1.3, Stage 3
- [Step Functions service quotas](https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html)
- [Temporal Cloud pricing](https://temporal.io/pricing)

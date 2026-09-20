# T-102 · Stop blocking the event loop in the Postgres repository

**Stage** 1 · **Type** work · **Status** done · **Owner** — · **Branch** `t-102-async-postgres-repository`

**Scope**
- `src/semanticgraph/adapters/outbound/postgres/**`
- `src/semanticgraph/application/ports/outbound/document_repository.py`
- `tests/integration/adapters/postgres/**`

**Blocked by** — · **Blocks** T-200

## Goal
`PostgresDocumentRepository` declares `async def` over blocking SQLModel `Session`
I/O. Every call blocks the event loop, so under load the API stalls on database
work while pretending to be asynchronous.

Move to `AsyncSession` throughout. Whichever way this resolves, apply it to every
outbound adapter — a port that is async in one adapter and sync in another is worse
than either.

## Acceptance
- [x] The repository uses `sqlalchemy.ext.asyncio.AsyncSession`; no blocking call sits inside an `async def`
- [x] `DocumentRepositoryPort` still expresses the same five operations
- [x] `InMemoryDocumentRepository` satisfies the port unchanged, or changes with it
- [x] The postgres integration suite passes standalone, not only in a full run
- [x] The architecture-fitness tests still pass

## Notes
Blocks T-200 because Stage 2's migrations land in the same package; finish this
before the schema chain opens. See ENTERPRISE_PLAN.md Stage 1, item 2c.

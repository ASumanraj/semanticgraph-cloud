# ADR-0002: Postgres as the canonical graph store, not Neo4j

## Status
**Accepted** — 2026-09-20. Supersedes the graph-store choice in [ADR-0001](0001-hexagonal-architecture.md).

## Deciders
- Platform Team

## Context

`ARCHITECTURE.md` and ADR-0001 assumed Neo4j behind a `GraphRepositoryPort`. The adapter was
never written — `adapters/outbound/neo4j/__init__.py` was a 0-byte file — so the decision was
still reversible when the research was done.

Two requirements drove the re-examination. **Tenant isolation** has to hold across graph
traversals, and **GDPR erasure** has to remove exactly one document's contribution to a derived
graph, transactionally.

What the research found:

- **Neo4j Aura caps multi-database at 5 databases per GB of RAM and 100 databases absolute**,
  regardless of instance size; it requires Business Critical tier or above and is still a Preview
  feature under Experimental Service Terms. The smallest instance reaching that cap is
  ~$4,672/month — a **$47/tenant/month floor at perfect packing**, and ten instances (~$46,720/mo)
  at 1,000 tenants. For calibration, GitLab runs an 8M-node / 11M-edge graph on a ~$105/month
  instance.
- **Neo4j has no row-level-security equivalent.** Pooled isolation is an application-layer
  predicate on every hop of every traversal, and a multi-hop query that filters the seed but not
  the hops crosses the boundary. That class of bug is not statically verifiable.
- **The failure is empirical, not hypothetical.** getzep/graphiti issue #1676: concurrent
  multi-tenant ingestion wrote episodes into the wrong tenant's graph because the driver mutated
  shared state between database selection and write — 19 misplaced episodes across 5 tenants, in
  production.

## Decision

**Postgres is the system of record for the entire graph**: documents, chunks, mentions, facts,
entities, edges, vectors, resolution decisions, usage and audit. Edges live in an indexed table
with `tenant_id` as the leading column of every composite index. Vectors use `pgvector`. Graph
algorithms (Leiden, personalized PageRank) run offline in-process via `igraph`/`graspologic` over
a per-tenant subgraph loaded into memory.

Isolation is enforced by the engine: `FORCE ROW LEVEL SECURITY`, an application role that does not
own the tables, and tenant context set with `SET LOCAL` inside the transaction.

A dedicated graph engine remains available later as a **derived read-model** — a projection built
from Postgres, never a second source of truth — for any single tenant whose graph outgrows this.
`adapters/outbound/graphprojection/` holds that seam.

## Rationale

1. **The retrieval shape is bounded neighborhood expansion, not deep traversal.** Vector-search
   seeds → 1–3 hop expansion → rank → assemble. Indexed relational joins are competitive in that
   regime; index-free adjacency dominates at 6+ hops, which this product does not do.
2. **RLS fails closed.** A forgotten predicate returns zero rows instead of another tenant's data.
   Every alternative in the comparison fails open. Measured overhead is ~3.6 ms vs 3.2 ms for
   100k rows across 1,000 tenants, provided `tenant_id` leads every composite index.
3. **One transactional store makes assertion-counted deletion tractable.** Removing a document's
   exact contribution requires joining fact → assertion → chunk → document and deleting facts with
   no remaining support, atomically. Postgres-as-truth plus Neo4j-as-truth makes that a dual-write
   consistency problem on the one operation that cannot be got wrong.
4. **Per-tenant marginal cost approaches zero**, which the developer-platform wedge requires.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **Neo4j, database-per-tenant** | Breaks at tenant #101; ~$47/tenant/month floor; Preview feature |
| **Neo4j, single DB + `tenant_id`** | Isolation is a code-review problem forever, with no engine backstop |
| **Neptune Analytics** | One vector index per graph, dimension fixed at creation, and vector writes are documented as "non-atomic and not isolated" |
| **FalkorDB** | **SSPLv1** — its own docs state that offering the functionality as a service requires releasing the complete service's source. Would need a signed commercial license before any code is written against it |
| **ArangoDB** | BUSL 1.1 with a 100 GiB community cap |
| **Memgraph** | BSL 1.1 |
| **Kùzu** | Repository archived 2025-10-10 following an Apple acquisition; GitLab had to migrate off it mid-project |
| **Dgraph** | Apache 2.0 since v25, but twice-acquired since 2023; DQL rather than Cypher |
| **Apache AGE** | Viable fallback if Cypher is genuinely wanted — same Postgres, same RLS — but variable-length path queries are its documented weak spot and releases trail Postgres major versions |

## Consequences

**Accepted costs.** No Cypher; queries are recursive CTEs and, more often, plain 2-hop joins. No
Neo4j GDS implementations of graph algorithms. A tenant with a 100M-edge densely-connected graph
running 6-hop queries will eventually need the projection escape hatch.

**Required discipline.** `tenant_id` goes on every table from the first migration, including where
it looks redundant, as the leading index column. The projection boundary
(`project_tenant_graph(tenant_id, since_version)`) is defined now, while its target is a no-op —
retrofitting it after two systems have both been written to directly is a reconciliation nightmare.

## References
- [`docs/architecture/ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Parts 1.1–1.2, 2.5
- [Neo4j Aura: multiple databases](https://neo4j.com/docs/aura/managing-instances/multiple-databases/)
- [Neo4j pricing](https://neo4j.com/pricing/)
- [Neptune Analytics vector index limits](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-index.html)
- [FalkorDB license](https://docs.falkordb.com/References/license.html)
- [getzep/graphiti issue #1676](https://github.com/getzep/graphiti/issues/1676)

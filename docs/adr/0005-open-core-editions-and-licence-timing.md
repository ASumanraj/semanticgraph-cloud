# ADR-0005: Open correctness, paid operations, and the licence decision deferred

## Status
**Accepted as a boundary rule** — 2026-09-21. The **licence choice is deliberately open** and
is not decided here.

## Deciders
- Platform Team

## Context

Enterprise infrastructure products commonly ship a self-hostable core, a managed cloud, and paid
enterprise controls (SSO, audit, support). GitLab and Grafana Enterprise are the usual examples;
this ADR did not re-check their current tiers, so treat them as the pattern, not as citations.

Two facts about this product shape the split.

**Its differentiator is checkable.** The value is a record where every fact points at the exact
sentence that supports it, corrections can be reversed, and deletion is precise
([`ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Part 0.1). A buyer can only believe
those properties if they can inspect them. If the correctness model were paid-only, the cloud
product would look like a black box and the self-hosted edition would look like a demo.

**Several model dependencies are hosted-only.** An air-gapped or regulated customer cannot send
documents to a vendor API, so any dependency with no local alternative cannot be required.

## Decision

1. **The correctness model is open and never paywalled.** That covers character-level provenance,
   assertion-counted deletion, the resolution decision log with human precedence, immutable ontology
   versions, bi-temporal validity, and the **tenant-aware schema** — `tenant_id` on every table and
   the row-level-security policies. No paid feature may be required to satisfy any of the five
   irreversible rules.
2. **Paid value is operations, governance, deployment and support.** Not correctness.
3. **Four editions:**

   | Edition | What it contains |
   |---|---|
   | Community | Single-tenant core: ingestion, extraction, provenance, temporal facts, decision log, deletion, a basic API |
   | Cloud | Managed Postgres, workers, model routing, autoscaling, backups, monitoring, usage metering |
   | Enterprise self-hosted | SSO and SCIM, advanced RBAC, audit export, customer-managed keys, air-gapped mode, high availability, upgrades, SLA and support |
   | Dedicated cloud | A single-tenant deployment we operate: private networking, data residency, custom limits |

4. **The tenant-aware schema stays in the open tree.** Community runs the same schema with one
   tenant, so the editions cannot drift structurally. What is paid is *operating many tenants
   safely*: provisioning, per-tenant quotas and spend caps, isolation administration, the admin
   console.
5. **Paid-eligible code lives in its own packages**, so a future split is a directory boundary and
   not a refactor. `control/` already holds usage, audit and quota. **Decide which of them are
   paid-eligible before T-208 (audit) and T-210 (quota) are written.** Whether the contracts
   ontology pack and the registry integrations are open or paid is left open until the pack exists.
6. **Every model dependency needs a local or customer-hosted alternative** before it can be
   required: extraction, the verifier, embeddings and parsing. A hosted-only vendor may be an
   optional provider behind a port, never a requirement.
7. **Licence timing.** Nothing is open-sourced until the contracts slice runs end to end; a
   half-built pipeline earns no adoption and spends the launch. **SSPL and BSL are ruled out now**,
   consistently with ADR-0002, which rejected FalkorDB because SSPL would force us to release our
   whole service. **Apache-2.0 versus AGPL-3.0 stays open**: Apache maximises adoption, AGPL
   protects against a hosted fork. That is a commercial and legal decision to take after the first
   useful release.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **Open everything** | No revenue path beyond services, which is the margin problem the plan set out to avoid |
| **Paywall the correctness features** | Customers cannot inspect the trust claims, and the cloud looks like a black box |
| **Paywall multi-tenant isolation** | Community and enterprise would diverge in the schema itself; only the *operation* of many tenants is paid |
| **SSPL or BSL** | Developers in this space filter them out, and adopting one contradicts our own reason for rejecting FalkorDB |

## Consequences

**Open-sourcing the correctness model is a bet, not a free choice.** A competitor such as
Graphiti (Apache-2.0) could copy the design. Our judgement is that retrofitting is expensive for
systems whose merges destroy information — the same irreversibility argument as the five rules —
but that is a judgement and not a measurement.

**The defensible product is the whole guarantee**, plus what took domain work and is not obvious
from reading source: the contracts ontology, the registry integrations, and running it safely
at scale. That is why the plan now says to sell the record and not the pipeline.

**Revisit when:** the contracts slice works end to end (licence), a design partner asks for
self-hosting (Enterprise self-hosted scope), or T-208 is about to be written (package boundary).

## References
- [`docs/architecture/ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Part 0.1–0.3
- [ADR-0002](0002-postgres-as-the-graph-store.md) — the FalkorDB and SSPL reasoning
- [ADR-0004](0004-external-knowledge-formats-are-projections.md)

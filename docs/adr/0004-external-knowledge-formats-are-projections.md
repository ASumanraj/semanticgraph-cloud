# ADR-0004: External knowledge formats are projections, not canonical storage

## Status
**Accepted** — 2026-09-20.

## Deciders
- Platform Team

## Context

Google Cloud published the **Open Knowledge Format (OKF)** in June 2026: a bundle is a
directory of Markdown files with YAML frontmatter, only `type` is required, and concepts
link to each other with ordinary Markdown links. It is vendor-neutral, agent-readable and
deliberately does not prescribe storage or query infrastructure.

Read from the spec (`okf/SPEC.md`) and the project's issue tracker on 2026-09-20:

- **It has already changed.** v0.2 (late July 2026) added `sources`, `verified` trust
  tiers, `status` and `stale_after`, and **broke v0.1** — `timestamp` became
  `generated: {by, at}` and body citations moved to frontmatter. Issue #24 reports that
  `okf_version: "0.2"` still names two documents.
- **It is converging on our territory.** Open proposals include deletion semantics (#11),
  typed, directed, trust-bearing relationships (#16), query-time semantics for
  `supersedes` and `contested_by` (#22) and a `refuted` trust state (#13). Google's
  announcement also mentions an optional erasure conformance profile.
- **Extra keys are advisory.** Producers MAY add any key; consumers SHOULD preserve
  unknown keys and MUST NOT reject them. There is no namespacing and no registry.
- **It records, it does not enforce.** Links are untyped. Multi-tenancy and access control
  are not addressed. `sources` is a claim made by whoever wrote the file.

What the format cannot carry natively is exactly what this product is for: character-level
evidence spans, a retractable decision history, bi-temporal validity, tenant isolation and
transactional deletion.

## Decision

1. **Postgres stays canonical.** No external format becomes storage.
2. **Two artifacts, not one.** A **native, versioned, lossless archive** is the only format
   used for backup, migration and audit. External formats are **projections** generated from
   it, and each projected item references its archive id and content hash.
3. **Projections are pinned.** Each adapter targets one explicit spec version, sits behind an
   outbound port, and follows the published spec — never an open proposal.
4. **Imported trust is a claim, not a decision.** An imported `verified: human-reviewed`
   means someone asserted it in the source bundle. It may influence ranking or review
   priority. It never receives Rule 3 precedence, which belongs only to decisions made in
   this system by an authenticated user.
5. **Import proposes; it never mutates.** An import lands in a quarantine namespace as an
   ontology proposal. Free-form `type` values and untyped links are normalised and approved
   by a human, then published as a new immutable ontology version (Rule 5).

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **OKF as the internal model** | It cannot express spans, decisions, validity windows or tenancy, and it cannot enforce any of them |
| **A sidecar inside the OKF bundle as the lossless format** | Depends on every consumer preserving unknown keys, which the spec says SHOULD, not MUST |
| **Ignore it** | It is backed by Google and aimed at exactly how agents consume knowledge; a buyer may name it in a requirements document |

## Consequences

**An export is a snapshot outside our deletion cascade.** Rule 4 reaches embeddings, caches,
summaries and fixtures; it cannot reach a bundle sitting in a customer's git repository.
Every export therefore carries a snapshot id and timestamp, and the DPA must state that
exports are point-in-time copies the customer is responsible for.

**The projection is lossy and is never a backup.** Spans, decision history, temporal
intervals and tenant-scoped ids survive only in the native archive.

**No field mapping is written here on purpose.** The spec broke compatibility once in three
months; a mapping belongs in the ticket that builds the adapter, against whatever version is
current then.

**Unresolved: whether to contribute span-level provenance upstream.** It would make the
format richer and make our differentiator easier to export losslessly; it would also make
the differentiator a commodity. That is a product-strategy decision, not an architecture
one, and it is deliberately left open.

**When to build the adapter:** after the contracts slice works end to end, and when a buyer
names OKF or a design partner runs agents on Google Cloud. Until then this ADR exists only
to stop OKF becoming the internal model by accident.

## References
- [OKF specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [OKF issue tracker](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues)
- [Google Cloud: OKF v0.2 adds trust signals](https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals)
- [`docs/architecture/ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Part 2 (the five irreversible rules)

# Superseded architecture documents

These describe the pre-research design and are kept for provenance only. Where they disagree with
[`../ENTERPRISE_PLAN.md`](../ENTERPRISE_PLAN.md), the plan is correct.

| Document | Superseded because |
|---|---|
| `ARCHITECTURE.md` | Specified Neo4j and Celery, and a directory layout with five scaffolds that no longer exist. See [ADR-0002](../../adr/0002-postgres-as-the-graph-store.md) and [ADR-0003](../../adr/0003-temporal-for-the-document-pipeline.md) |
| `SYSTEM_DESIGN_DOC.md` | Neo4j-based graph layer |
| `Architectural_Interrogation_Answers.md` | Neo4j-based graph layer |
| `ECC_AWS_Infrastructure_Specs.md` | Neo4j-based infrastructure sizing |

`Extraction_Pipeline_Spec.md` stayed in `../` — it is store-agnostic and still applies, though
Stage 3 of the plan extends it with the GLiNER prefilter, ontology snippets and mandatory spans.

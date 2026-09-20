# Pre-built Commercial Contracts Vertical Ontology Pack

This pack provides the pre-built, production-ready schema for extracting, resolving, and querying enterprise commercial agreements.

## Strategic Purpose

As detailed in `docs/architecture/ENTERPRISE_PLAN.md` Part 0.2:
> "A multi-tenant knowledge-graph substrate, sold as an API to companies building AI products, with one pre-built vertical ontology pack (commercial contracts) shipped as proof that a customer never needs a forward-deployed engineer to get value."
> "Shipping a working pre-built ontology is the proof that you are software, not consulting."

## Schema Elements

### Entity Types
- **`Company`**: Counterparties, vendors, clients, parent entities (resolvable to LEI/CIK).
- **`Person`**: Executive signatories, authorized representatives.
- **`Contract`**: Master Services Agreements (MSAs), Statements of Work (SOWs), Amendments, NDAs.
- **`Obligation`**: Payment terms, indemnifications, SLA covenants, delivery deadlines.
- **`Jurisdiction`**: Governing laws and dispute resolution venues.

### Relation / Edge Types
- `PARTY_TO`: `(Company) -> (Contract)`
- `SIGNATORY_OF`: `(Person) -> (Contract)`
- `HAS_OBLIGATION`: `(Contract) -> (Obligation)`
- `OBLIGATED_TO`: `(Obligation) -> (Company)`
- `GOVERNED_BY`: `(Contract) -> (Jurisdiction)`
- `AMENDS`: `(Contract) -> (Contract)`
- `SUPERSEDES`: `(Contract) -> (Contract)`

## Corpus Documents

The `corpus/` folder includes realistic enterprise contracts demonstrating:
- Multiple documents asserting shared facts (e.g. counterparty identity and governing law).
- Verbatim evidence spans with exact character offsets.
- Resolution across variant entity names (e.g., `"Acme Global Solutions LLC"` vs `"Acme Global Solutions"`).
- Non-destructive unmerging and human adjudication overrides.
- Assertion-counted deletion and single-transaction cascading garbage collection.

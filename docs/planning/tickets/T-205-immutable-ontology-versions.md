# T-205 · Immutable, versioned ontologies

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-205-immutable-ontology-versions`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/models/entities.py`
- `src/semanticgraph/adapters/outbound/postgres/**`

**Blocked by** T-204 · **Blocks** —

## Goal
Editing an ontology publishes a new version rather than mutating the old one, and
every extraction run records the `ontology_version` it ran under. Irreversible rule
5. Edit in place and every fact extracted under the old version becomes
unattributable — "why does this entity have this type?" stops being answerable.

## Acceptance
- [ ] Ontology versions are immutable once published
- [ ] Editing creates a new version and leaves prior versions readable
- [ ] Every extraction run stores its `ontology_version`
- [ ] A fact can be traced to the ontology version that produced it
- [ ] A test proves a published version cannot be modified

## Notes
Also the precondition for selective re-extraction: without versions, an ontology
change means re-extracting everything at full cost.

# T-205 · Immutable, versioned ontologies

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-205-immutable-ontology-versions`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/models/entities.py`
- `src/semanticgraph/adapters/outbound/postgres/**`
- `tests/unit/domain/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-204 · **Blocks** —

## Goal
Editing an ontology publishes a new version rather than mutating the old one, and
every extraction run records the `ontology_version` it ran under. Irreversible rule
5. Edit in place and every fact extracted under the old version becomes
unattributable — "why does this entity have this type?" stops being answerable.

## Acceptance
- [x] Ontology versions are immutable once published
- [x] Editing creates a new version and leaves prior versions readable
- [x] Every extraction run stores its `ontology_version`
- [x] A fact can be traced to the ontology version that produced it
- [x] A test proves a published version cannot be modified

## Notes
Also the precondition for selective re-extraction: without versions, an ontology
change means re-extracting everything at full cost.

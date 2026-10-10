# T-228 · The demo runs on Postgres and says what produced its output

**Stage** 3 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-228-real-stack-demo`

**Scope**
- `docker-compose.real.yml` (new; the existing `docker-compose.yml` is not edited)
- `src/semanticgraph/adapters/inbound/api/v1/system.py` (new), `src/semanticgraph/adapters/inbound/api/app.py` (router registration only)
- `src/semanticgraph/composition/container.py` (expose a read-only description of the active profile and extractor; no wiring change)
- `frontend/src/**` (a status banner only), `frontend/e2e/**`
- `tests/integration/demo/**`, `tests/unit/composition/**`
- `docs/design/**` (screenshots), `README.md` (run instructions)

**Blocked by** — · **Blocks** any demo shown to a buyer

## Why

A visitor who runs the stack today gets a working upload and graph, but everything is held in memory (the default
compose profile is `SEMANTICGRAPH_ADAPTERS=inmemory`; a restart empties it) and every entity is named "Entity from
chunk N" by the deterministic test extractor, with nothing on screen saying so. The Postgres persistence, isolation and
deletion are real and tested, but the demo never touches them. A demo must not present placeholder output as extraction.

## What this ticket does, and does not do

**Does:** (1) a one-command stack that uses the Postgres adapters, so documents, chunks, entities, edges and spans are
persisted and survive a restart; (2) a truthful status surface: the API says which profile and which extractor are
active, and the page shows it.

**Does not:** add a real extractor. With no model key the output is still placeholder text, and the banner says so in
words ("Placeholder extractor: entity names are not extracted from your document"). A real extractor is
[T-229](T-229-dev-only-open-model-extractor.md), which needs a decision first. This ticket proves **persistence and
honest labelling only**.

## Design

1. `docker-compose.real.yml` overrides the api and worker to `SEMANTICGRAPH_ADAPTERS=postgres`, runs `alembic upgrade
   head` before the API starts, and uses the same Postgres service. The default `docker-compose.yml` stays as is so
   nothing running on the founder's machine changes unless asked.
2. `GET /api/v1/system` (no tenant header needed, no secrets) returns
   `{ "profile": "inmemory"|"postgres", "persistent": bool, "extractor": { "kind": "placeholder"|"model", "model_id": str|null, "terms": "evaluation-only"|null } }`.
   `kind` is `placeholder` exactly when the deterministic gateway is the one in use; `model_id` is read from the
   gateway in use, never from a config string.
3. The frontend shows one banner from that response. `placeholder`: states that entity names are placeholders and
   that the graph shows the quoted source text. `model`: names the model and, when `terms` is set, says the output
   comes from an evaluation endpoint. If `/system` fails, show "status unavailable", never a green state.
4. The chunker is not changed here, but the ticket records what it does (splits on blank lines, no size cap, no
   overlap) so a real-extractor run on a long unbroken text does not silently send one huge chunk. T-229 owns that.

## End-to-end checks (all required; real infrastructure, not fakes)

- [ ] **Rows by SQL.** Post a synthetic contract to `POST /api/v1/documents/ingest`, wait for the worker, then query
  Postgres directly: `documents`, `semantic_chunks`, `entities`, `edges`, `evidence_spans` have rows, each with the
  right `tenant_id`, non-null `chunk_id` and span offsets, and the stored quote equals the source substring at those
  offsets.
- [ ] **Restart persistence.** `docker compose restart api worker`; `GET /api/v1/graph` returns the same node ids.
- [ ] **Isolation over HTTP.** A second tenant id sees an empty graph and gets 404 for the first tenant's document.
- [ ] **Deletion.** `DELETE /api/v1/documents/{id}`; SQL shows the document's chunks, assertions and entities gone and
  a fact asserted by a second document still present.
- [ ] **Idempotent retry.** Ingesting the same file twice does not duplicate assertions (T-222 behaviour, proven on the
  running stack).
- [ ] **Truthful label.** Playwright, in a real browser against this stack: upload, then assert the banner reads
  "Placeholder extractor" and that the page never shows an entity name from the placeholder extractor without the
  banner present. A second test stubs `/system` as `model` and asserts the model id and evaluation-terms line.
- [ ] **Status fails safe.** With `/system` returning 500 the banner shows "status unavailable".
- [ ] Screenshots of the upload page and the explorer with a selected node, at 1440 and 390 px, with the banner,
  attached to the PR.
- [ ] `ruff check .` and `ruff format --check .` clean; fast suite, isolation proofs and control-plane proofs green;
  frontend lint, build and E2E green; CI green.

## Documents allowed

Synthetic contracts written for the repo only. No customer or founder-supplied files. Nothing here calls a model.

## Notes

- Do not start, stop or rebuild containers the founder is running, and do not edit `docker-compose.yml`. Use a
  separate compose project name (`-p semanticgraph-real`) and non-default ports (for example 8013 and 3013) so the two
  stacks cannot collide; the founder's machine has other projects on 3000 and 8000.
- The unsigned `X-Tenant-ID` header is not authentication (Stage 5). Say so in the README run instructions.
- Read `frontend/AGENTS.md` first.

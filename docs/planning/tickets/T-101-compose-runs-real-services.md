# T-101 · Run the real API and worker in docker compose

**Stage** 1 · **Type** work · **Status** done · **Owner** agy · **Branch** `t-101-compose-runs-real-services`

**Scope**
- `docker-compose.yml`
- `api.Dockerfile`
- `frontend.Dockerfile`
- `tests/unit/test_compose_config.py`

**Blocked by** — · **Blocks** T-103, T-104

## Goal
`api` and `worker` both run `python -c 'import time; sleep(3600)'`, so nothing in the
compose stack actually serves. Boot the real processes. This unblocks every
end-to-end proof, which currently has nothing to point at.

`SEMANTICGRAPH_ADAPTERS` already selects the adapter set, so the API can come up
against in-memory adapters with no database wiring in this ticket.

## Acceptance
- [x] `api` runs uvicorn against `semanticgraph.adapters.inbound.api.app:app`
- [x] `worker` runs the Celery app from `adapters/inbound/workers/celery_app.py`
- [x] `docker compose up` then `curl localhost:8000/health` returns `{"status":"healthy"}`
- [x] `POST /api/v1/documents/ingest` with an `X-Tenant-ID` header returns 200
- [x] `frontend` builds and serves on 3000
- [x] No service command contains `sleep`

## Verification

Run against the live stack on 2026-09-20, not inferred from the compose file:

```
GET  localhost:8000/health                → {"status":"healthy"}            HTTP 200
POST /api/v1/documents/ingest             → document_id, status extracting  HTTP 200
     (X-Tenant-ID: 11111111-…-555555555555)
GET  localhost:3000                       → <title>SemanticGraph Cloud</…>  HTTP 200
```

`docker compose ps`: api, postgres and redis healthy; frontend up.

`tests/unit/test_compose_config.py` asserts the compose and Dockerfile
*definitions*. It is a config lint, not evidence the services start — the three
lines above are that evidence.

## Notes
`api.Dockerfile` still carries the mock `CMD`. Compose has `postgres` and `redis`
already; leave them, T-103 uses the postgres service.

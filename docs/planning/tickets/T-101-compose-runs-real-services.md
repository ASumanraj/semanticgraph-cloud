# T-101 · Run the real API and worker in docker compose

**Stage** 1 · **Type** work · **Status** claimed · **Owner** agy · **Branch** `t-101-compose-runs-real-services`

**Scope**
- `docker-compose.yml`
- `api.Dockerfile`
- `frontend.Dockerfile`

**Blocked by** — · **Blocks** T-103, T-104

## Goal
`api` and `worker` both run `python -c 'import time; sleep(3600)'`, so nothing in the
compose stack actually serves. Boot the real processes. This unblocks every
end-to-end proof, which currently has nothing to point at.

`SEMANTICGRAPH_ADAPTERS` already selects the adapter set, so the API can come up
against in-memory adapters with no database wiring in this ticket.

## Acceptance
- [ ] `api` runs uvicorn against `semanticgraph.adapters.inbound.api.app:app`
- [ ] `worker` runs the Celery app from `adapters/inbound/workers/celery_app.py`
- [ ] `docker compose up` then `curl localhost:8000/health` returns `{"status":"healthy"}`
- [ ] `POST /api/v1/documents/ingest` with an `X-Tenant-ID` header returns 200
- [ ] `frontend` builds and serves on 3000
- [ ] No service command contains `sleep`

## Notes
`api.Dockerfile` still carries the mock `CMD`. Compose has `postgres` and `redis`
already; leave them, T-103 uses the postgres service.

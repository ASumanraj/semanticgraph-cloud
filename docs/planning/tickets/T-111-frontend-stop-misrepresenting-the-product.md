# T-111 · Make the frontend stop misrepresenting the product

**Stage** 1 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-111-frontend-honesty`

**Scope**
- `frontend/**`

**Blocked by** — · **Blocks** —

## Goal

The console shows things that are not true. Each of these was found by reading the code
(T-902) and re-checked on `main` at `91775e8`:

| Where | What it does |
|---|---|
| `components/GraphExplorer.tsx` | fetches a hardcoded `http://localhost:8000/graph` and sends a fake `tenant_id: "tenant-123"` header — the unsigned-header pattern Stage 5 forbids |
| `components/AuthGuard.tsx` | hardcodes `currentUserRole = "Super Admin"`, so it looks like an access check and authorizes nothing |
| `app/page.tsx` | advertises "High-Speed Celery Workers" (replaced by ADR-0003) and `"verification": "100% Mathematically Proven"` |
| `app/dashboard/page.tsx` | a fabricated activity feed naming a Gemini model this architecture does not use |
| two sidebars | link to routes that do not exist and omit ontology, evaluations and chat |

A console that displays invented data and a fake permission check is worse than an empty
one, because a buyer or a design partner will believe it.

**This ticket removes and corrects. It adds no screens.** The rule for this project is that
a screen waits until the API behaviour behind it exists (T-110 is the first of that).

## Acceptance

- [x] `GraphExplorer` reads its base URL from `NEXT_PUBLIC_API_URL` and sends no fabricated tenant header; with nothing to show it renders a truthful empty state
- [x] `AuthGuard` is removed, or fails closed until real auth exists — it never grants a role it was not given
- [x] The landing page no longer names Celery, and the "100% Mathematically Proven" claim is gone
- [x] Every dashboard number and feed entry is real or replaced with an honest empty state; nothing names a provider the system does not call
- [x] One sidebar remains and every link resolves
- [x] `chat` and `connectors`, which appear in none of the eleven consoles T-902 compared, are removed unless the owner says otherwise
- [x] `DocumentUpload` posts to the API's real route, `POST /api/v1/documents/ingest`, with the JSON body the API expects (`filename`, base64 `content`) and a tenant header it accepts. Today it posts to `/upload`, which does not exist
- [x] The Playwright upload journey runs against the **running API** with no `page.route` stub, and asserts the document the API reports afterwards — this is the criterion T-104 ticked and did not meet
- [x] `npm run lint` and `npm run build` are clean

## Notes

Disjoint from every backend ticket, so it can run beside them. See
[`docs/research/developer-product-surface.md`](../../research/developer-product-surface.md)
for the console comparison and the recommended surface.

## Review, verified 2026-09-22

Reviewed PR #11 (`d4e55db`) against `t-111-frontend-honesty`. Ran the real Playwright test myself
(`npm run test:e2e`, dual `webServer`: a genuine `uvicorn` process plus `next dev`, no `page.route`
stub) — 1 passed, matching the report, and I watched it drive a real `POST
/api/v1/documents/ingest` and assert the real 200 response and UI confirmation. Also ran `npm run
lint` (clean) and `npm run build` (clean, exactly the 5 routes the new `Sidebar.tsx` links to:
`/dashboard`, `/dashboard/explorer`, `/dashboard/ontology`, `/dashboard/evaluations`,
`/dashboard/settings` — no dead links, `chat`/`connectors` genuinely gone). `AuthGuard.tsx` is
deleted, not just neutered.

**One gap worth recording, not blocking this PR:** `GraphExplorer.tsx` now fetches
`/api/v1/graph` with no fabricated header, which satisfies the letter of the acceptance criterion
(truthful empty state when there's nothing to show) — but I checked, and **no such route exists on
the backend at all**. The only inbound routes today are `POST /api/v1/documents/ingest` and `GET
/api/v1/facts/{fact_id}`; the `SearchEngine`/subgraph-retrieval use case exists in
`application/use_cases/search_subgraph.py` and is built into `Container`, but nothing wires it to
HTTP. So the Graph Explorer screen is now honest about having nothing to show, but it can *never*
have anything to show until a real subgraph route exists — that's backend work, outside this
ticket's `frontend/**` scope. Worth a new ticket (`GET /api/v1/subgraph` or similar, wiring
`SearchEngine` to HTTP) rather than silently living with an explorer screen that's structurally
unable to show data.

Full suite unaffected (backend untouched by this PR). Accepted. Status set to done.

# T-111 · Make the frontend stop misrepresenting the product

**Stage** 1 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-111-frontend-honesty`

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

- [ ] `GraphExplorer` reads its base URL from `NEXT_PUBLIC_API_URL` and sends no fabricated tenant header; with nothing to show it renders a truthful empty state
- [ ] `AuthGuard` is removed, or fails closed until real auth exists — it never grants a role it was not given
- [ ] The landing page no longer names Celery, and the "100% Mathematically Proven" claim is gone
- [ ] Every dashboard number and feed entry is real or replaced with an honest empty state; nothing names a provider the system does not call
- [ ] One sidebar remains and every link resolves
- [ ] `chat` and `connectors`, which appear in none of the eleven consoles T-902 compared, are removed unless the owner says otherwise
- [ ] `DocumentUpload` posts to the API's real route, `POST /api/v1/documents/ingest`, with the JSON body the API expects (`filename`, base64 `content`) and a tenant header it accepts. Today it posts to `/upload`, which does not exist
- [ ] The Playwright upload journey runs against the **running API** with no `page.route` stub, and asserts the document the API reports afterwards — this is the criterion T-104 ticked and did not meet
- [ ] `npm run lint` and `npm run build` are clean

## Notes

Disjoint from every backend ticket, so it can run beside them. See
[`docs/research/developer-product-surface.md`](../../research/developer-product-surface.md)
for the console comparison and the recommended surface.

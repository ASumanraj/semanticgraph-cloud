# T-230 · The default stack works out of the box, and a first visit explains itself

**Stage** 3 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-230-default-stack-first-visit`

**Scope**
- `docker-compose.yml`, `frontend.Dockerfile`, `frontend/next.config.ts`
- `frontend/src/**`, `frontend/e2e/**`, `docs/design/**`
- `README.md`

**Blocked by** — · **Blocks** any demo shown to a buyer. Do not run in parallel with T-229 on `frontend/src/**` or `README.md`; T-229 owns neither beyond its banner line, but rebase before opening the PR.

## Problem 1 (bug, reproduced 2026-10-15)

On the default stack (`localhost:3003`) the explorer shows "Couldn't load the graph". The browser calls `/api/v1/graph`
on the frontend, Next proxies it to `BACKEND_API_URL` or `NEXT_PUBLIC_API_URL` or `127.0.0.1:8000`, and inside the
frontend container nothing listens on 127.0.0.1:8000 (`ECONNREFUSED` in the container log). The API itself is healthy
on 8003. `docker-compose.real.yml` already sets `BACKEND_API_URL=http://api:8000`; the default file does not.
Rewrites are resolved when Next builds, so the variable is needed at build and run time.

Fix: set it in the default compose and the Dockerfile build, and add a test that fails when the frontend cannot reach the
API through its own proxy (`GET /api/v1/system` through the frontend port returns 200, not 500). The explorer's error
state must say what failed, for example "The API did not respond", with the Retry button; never a generic message.

## Problem 2: a first visit explains nothing

Someone who opens the site sees an empty console. Design a first-visit path, using only what the API returns and
honest labels (T-221 honesty rule, T-228 banner stays):

1. **Empty state that teaches:** one sentence on what the product does, one on what this demo is (placeholder or model
   extractor, taken from `/api/v1/system`), and one primary action.
2. **"Try a sample" button** that uploads a small synthetic contract shipped in the repo, so nobody needs a file to see
   the result. Mark the document as a sample.
3. **Provenance first:** after the sample loads, select a node automatically and open the evidence panel, since the
   quote and span for each result is the differentiator.
4. **Plain language:** no jargon in labels (no "Substrate", "Hop", "kind raw"); depth and filters get one-line help text.
5. **Error and loading states** for upload, graph and system status, each saying what happened and what to do.
6. **Keep it small:** no new screens for features that do not exist; no claims the backend cannot support.

Review against the Penpot boards and T-221; where this ticket changes the design, update `docs/design/` and say so.

## End-to-end checks

- [ ] Fresh clone, `docker compose up --build`, open `localhost:3003`: graph area loads without error (Playwright, real
  browser, default compose).
- [ ] Frontend-proxied `GET /api/v1/system` returns 200 on the default stack.
- [ ] Click "Try a sample": nodes appear, the evidence panel opens, quote equals the source text at the shown offsets.
- [ ] With the API stopped, the page shows "The API did not respond" and Retry recovers when it returns.
- [ ] Screenshots at 1440 and 390 px of: first visit, after sample, error state.
- [ ] A short written walkthrough of the first visit in the PR, written as a visitor would see it.
- [ ] `ruff`, frontend lint/build/E2E, CI green.

## Notes

- Do not stop, rebuild or restart the founder's running containers; use a separate compose project name and ports.
- Synthetic documents only.

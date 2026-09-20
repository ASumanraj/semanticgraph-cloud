# T-104 · Drive the real upload control in a browser

**Stage** 1 · **Type** work · **Status** open · **Owner** — · **Branch** `t-104-playwright-upload-journey`

**Scope**
- `frontend/**`

**Blocked by** T-101 · **Blocks** —

## Goal
`frontend/` has a `DocumentUpload` component and no test that has ever rendered it.
Stand up Playwright and drive the actual control against a running API, so a UI
change that breaks upload fails a build instead of a demo.

## Acceptance
- [ ] Playwright installed and configured in `frontend/`
- [ ] One spec uploads a file through the real UI and asserts what the user sees afterwards
- [ ] The request reaching the API is asserted, not stubbed away
- [ ] Page objects rather than raw selectors, per the `e2e-testing` skill
- [ ] `npm run test:e2e` runs it; CI runs it in the `frontend` job
- [ ] A screenshot artifact is produced on failure

## Notes
Use the `e2e-testing` and `frontend-patterns` skills. The app is Next 16 / React 19
/ Tailwind 4 with reactflow and recharts; `nextjs-turbopack` covers dev-server
behaviour.

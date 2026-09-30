# T-221 · Frontend design pass: tokens, the graph explorer, and restrained motion

**Stage** 3 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-221-frontend-design-pass`

**Scope**
- `frontend/**`
- `docs/design/**` (exported Penpot frames, the only design artefacts kept in the repo)

**Blocked by** the reviewer's look at the Penpot boards (screenshot review, see Design source) and
[T-226](T-226-ci-installs-from-uv-lock.md) only if it lands in the same window (both touch CI paths indirectly; no file overlap) · **Blocks** —

## Goal

Make the two screens that exist (upload, graph explorer) look and feel like a product, from a design
that was agreed before code. The graph explorer already shows the product's differentiator: the exact
quote and chunk id for a selected node. The design pass must make that panel the clearest thing on the
screen.

This ticket restyles what the API already returns. It does **not** add backend fields, new screens for
features that do not exist, or new claims.

## Design source

Penpot file "Dashboard UI Kit - Dashboard" (an imported community kit with our own page added), page
**SemanticGraph Screens**, boards **Graph Explorer** and **Graph Explorer - Empty State**, with a token
set `core` (page `#050810`, panel `#0A0F1E`, border `#1F2937`, text `#F8FAFC`, muted `#9CA3AF`, teal
`#2DD4BF`, cyan `#00FFFF`, purple `#C084FC`, error `#F87171`). The kit's own pages are a layout reference
only: its licence is unverified, so **do not copy its boards, icons or assets into the repository**.
Export the two boards as PNG into `docs/design/` and cite those, not the Penpot file, in the PR.

## The honesty rule (from T-111)

Every element on screen must come from a field the API returns, or be plainly a control. The graph route
returns, per node: `id`, `name`, `entity_type`, `kind`, and `provenance` (`chunk_id`, `start_offset`,
`end_offset`, `quote`); per edge: `id`, `source`, `target`, `edge_type`, `weight`, `valid_from`, `valid_to`,
`provenance`; and `truncated`. Nothing else. No golden-record badges, confidence numbers, assertion
counts, ontology versions, "tenant isolated" badges, or copy that says entities are resolved. Copy that
describes the pipeline must match what the running system does.

## Design

1. **Tokens once.** Map the Penpot tokens into the Tailwind v4 `@theme` block in `frontend/src/app/globals.css`
   (CSS variables) and use them everywhere; no hard-coded hex in components.
2. **Graph explorer.** Follow the boards: a sidebar (search, depth 1-3), the canvas, and a properties
   panel for the selected node or edge. Edge selection is new behaviour (React Flow supports it): show edge
   type, weight, valid from/to and quote. Show the `truncated` notice only when the response says so, and
   the empty state when there are no nodes.
3. **Interactions that explain the data.** All of these use only what the API already returns:
   - Hovering a node brightens it and its connected edges and dims the rest (client-side, from the edges
     in the response).
   - Clicking a node or an edge opens the properties panel with its quote and chunk id.
   - Double-clicking a node loads its neighbourhood with `GET /api/v1/graph?query=<name>&depth=1`; the
     new nodes ease in from the clicked node. Show a loading and an error state.
   - Search-as-you-type (debounced) and the depth control reload the graph, and nodes glide to their new
     positions instead of jumping.
   - Entity-type filter chips with counts, applied on the client.
   - Keyboard: `/` focuses search, arrow keys move between connected nodes, `Esc` clears the selection.
   - After an upload, the entities that appeared get a short "new" accent so the link between the upload
     and the graph is visible.
   - Edges are static; animate only on hover and selection. Remove the always-on flowing dashes and glow
     the component has today.
4. **Motion, restrained and on purpose.** Use `framer-motion` (already installed) for the panel sliding in,
   nodes easing in, and layout transitions; CSS for hover, focus and loading states. Keep durations short
   (about 150-250 ms), animate only `transform` and `opacity`, and honour `prefers-reduced-motion`. No
   looping decorative animation and no physics layout that never settles.
5. **Accessibility basics.** Text contrast of at least 4.5:1 against its background (check edges and muted
   text on `#050810`), visible focus rings, keyboard selection of nodes, and labels on the controls.
6. **Responsive.** The layout works at 1440 and at 390 px width (sidebar collapses, panel becomes a sheet).
7. Do not change the backend or the API contract. If a screen needs a field that does not exist, file a
   ticket instead.

## Acceptance

- [ ] Tokens live in `@theme` and no component hard-codes a colour
- [ ] Playwright tests, in a real browser against the running API, for: hover highlighting (neighbours emphasised, others dimmed), click-to-inspect showing the exact quote, double-click expansion adding nodes, a type filter hiding nodes, and keyboard navigation
- [ ] Real-browser Playwright screenshots of the upload screen, the explorer with a selected node, the explorer with a selected edge, the empty state and the truncated notice, at 1440 and at 390 px, attached to the PR and compared with the exported Penpot boards
- [ ] A test or a written check for each element in the honesty rule's list of API fields, and none for anything outside it
- [ ] The E2E suite still passes and leaves `git status` clean; the React Flow `nodeTypes`/`edgeTypes` warning is gone
- [ ] `prefers-reduced-motion` verified (animations off), contrast checked on edges and muted text
- [ ] `npm run lint` and `npm run build` clean; `ruff check .` clean; CI green

## Notes

The data in the running demo is still produced by the deterministic test extractor ("Entity from chunk
N"). That is a separate gap (a real-extractor demo) and is not solved here. Do not make placeholder data
look like real extraction: if the UI can tell, label it; if it cannot, say nothing it cannot support.
Read `frontend/AGENTS.md` first: this Next.js version has breaking changes and its docs are in
`node_modules/next/dist/docs/`.

## Parked ideas (need a backend change; do not build here)

Keep these for after [T-223](T-223-buyer-workflow-interviews.md) shows buyers care, each as its own ticket:
an **as-of time slider** (the API has no as-of parameter, and extracted edges probably have empty
`valid_from`/`valid_to`, so it would show nothing meaningful today); a **"what would deleting this
document remove?" preview** (needs a dry-run deletion endpoint; it demonstrates the deletion guarantee
directly); and **"view in source"** with the quote highlighted in the full chunk (needs a chunk-text
endpoint).

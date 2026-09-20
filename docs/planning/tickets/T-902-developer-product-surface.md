# T-902 · Design the product surface for a developer-first platform

**Stage** — · **Type** research · **Status** done · **Owner** claude · **Branch** `t-902-developer-product-surface`

**Scope**
- `docs/research/**`
- `docs/adr/**` (a new ADR, if the findings warrant one)

**Blocked by** — · **Blocks** —

## Question
`frontend/` already ships seven pages — landing, dashboard, chat, connectors,
evaluations, explorer, ontology, settings. Are those the right ones, in the right
order, for a developer-first API product?

Two things to settle:

1. **The surface.** What screens does an AI-infrastructure console actually need,
   and which of ours are missing or unnecessary? Specifically the three that are
   product rather than decoration here: the **ontology editor**, the **graph
   explorer**, and the **entity-resolution review queue** that Part 0.1 names as a
   differentiator no hyperscaler will build.
2. **Time to first value.** For a developer platform the first ten minutes decide
   adoption. What is the shortest path from landing on the site to a first
   successful API response, and what do the platforms that do this well put in it?

## Resolution
_Researched 2026-09-20._ Full report:
[`docs/research/developer-product-surface.md`](../../research/developer-product-surface.md).

Eleven consoles traced against their own docs (Pinecone, Weaviate Cloud, Zep, Supabase,
Neon, Clerk, Resend, Modal, LangSmith, Neo4j Aura, plus Stripe as the reference standard).

**The surface.** Seven screens are table stakes — API keys, usage/cost, request logs, a data
browser, team, billing, and a project switcher — and **five of them do not exist here**. Two of
our seven pages (`chat`, `connectors`) exist in no console in the comparison set. Four of the
seven are ten-line stubs, including the ontology page. The two sidebars link to five routes
that do not exist and to none of ontology, evaluations or chat.

**The three real screens.**
- *Ontology editor* — Palantir Foundry already proves the metaphor our rule 5 needs: a draft is
  a branch, publishing is a merge, an "ontology proposal" is a pull request. Version picker in
  the chrome (Neon's branch picker), form + round-tripping YAML, publish-as-diff. Zep, the
  closest competitor, is code-only with a read-only viewer and documents no versioning at all.
- *Graph explorer* — never render the graph, render a query result. Neo4j caps visualization
  queries at 10k records; reactflow will degrade far sooner. Search-then-expand, filters in a
  right drawer, bi-temporal sliders, and provenance-on-click, which no competitor can do.
- *Resolution review queue* — the rarest screen and the one worth building **first**. Steal
  LangSmith's queue mechanics, Splink's match-weight waterfall, Senzing's why/why-not, Reltio's
  five-up side-by-side and bulk actions, Zingg's decision-boundary ordering. Rule 3 gives us
  undo for free; advertise it.

**Time to first value.** Median ~4 steps; Clerk (one `init` command) and Neon (placeholder SQL
already in the editor, click Run) are fastest. Nobody hands out a live key pre-signup except
Stripe, which ships a working sample test key in every snippet — the cheapest high-leverage
trick available. The 2026 shift: the first step is now an agent step (Pinecone's recommended
quickstart is `claude plugin install pinecone`), which makes `llms.txt`, an MCP server and a CLI
table stakes rather than polish. Recommendation: a public demo key runnable from the landing
page, then a **pre-seeded contracts demo tenant** so the first action is reading an answer with
citations, not waiting on a pipeline. Upload is step two.

**What to cut.** Delete `chat` (build the query playground instead), `connectors`, `AuthGuard`
(hardcoded `"Super Admin"`), `components/Sidebar.tsx` and the fabricated dashboard. Demote
`evaluations` to internal. The landing page still sells Celery and "100% Mathematically Proven",
and `GraphExplorer` sends the unsigned `tenant_id` header Stage 5 forbids.

No ADR proposed — these are product decisions, not architectural ones. Follow-on tickets should
cover the onboarding path, the API-keys/usage screens, and the review queue.

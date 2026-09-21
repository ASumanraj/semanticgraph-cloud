# T-211 · Make the usage ledger fail loudly and price the models we use

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-211-usage-ledger-fail-loudly`

**Scope**
- `src/semanticgraph/control/usage/**`
- `alembic/**`
- `tests/unit/control/**`
- `tests/integration/control/**`

**Blocked by** — · **Blocks** T-210 (the spend cap reads period spend from this ledger)

## Goal

Three defects found reviewing T-207. Each was reproduced by running the code, not inferred.
T-207's acceptance list was met as written; the gaps are in what that list asked for.

**1 · It crashes on a real SDK response.** With prompt caching unused, the Anthropic SDK's
`Usage` object (anthropic 1.7.0) has `cache_read_input_tokens=None` and
`cache_creation_input_tokens=None`. The ledger's SDK branch passes those straight into
`calculate_cost_millicents`, which does `None * float` and raises `TypeError`. The tests feed
it dicts, so this has never fired — and the SDK object is the only path production has.

**2 · Unknown models get an invented price, silently.** For an unknown `model_id` or
`price_version` the cost function returns `input_tokens * 0.1 + output_tokens * 0.5` with no
error, ignores cache tokens, and the row is still stamped with a real-looking price version.
Run on 200k input / 200k output / 800k cache-read tokens: the known model prices at 320,000
millicents, a typo'd model id at 120,000.

The fallback equals Haiku 4.5's list price ($1 / $5 per million tokens) — so Sonnet 5 and
Opus 5 at the $2 / $10 and $5 / $25 recorded during research would be under-recorded about
2× and 5×. Worse, `PRICE_SCHEDULES` prices only `claude-3-7-sonnet` and `claude-3-5-haiku`,
none of the models `AGENTS.md` routes to, so **every real call would take the fallback**. The
list prices come from earlier research and should be re-read from the vendor.

**3 · Cost cannot be attributed to a document, run or user.** `usage_events` has no
`document_id`, `extraction_run_id` or `user_id`; the only place for them is free-text
`metadata_json`. Per-document cost — the $0.09 per document budget in the acceptance protocol
and the whole unit-economics model — cannot be queried. The table is append-only and never
back-filled, so the gap only widens with every row written.

**Design constraint.** `document_id` is a plain UUID with **no foreign key**. An immutable
ledger with a foreign key to `documents` would collide with T-206's cascade delete. Today
there is no collision only because there is no link at all. The ledger holds ids, never text.

## Acceptance

- [x] A test built from a real `anthropic.types.Usage` with unset cache fields records correctly — the SDK type, not a dict
- [x] `None` cache fields are treated as 0 in both the dict and the SDK branch
- [x] An unknown model or price version **never** produces a guessed price: it raises a typed error (`UnpricedModelError` / `UnknownPriceVersionError`). Choice: Raises typed errors to fail loudly at call site
- [ ] The price schedule covers every model the container's LLM gateway can route to, each price copied from the vendor's pricing page with the URL and date beside it, and a test fails if a routable model is unpriced
  - *Not met, reverted on review: the schedule prices Claude 3.x models and generic aliases at prices that match no current model, and none of `claude-haiku-4-5-20251001`, `claude-sonnet-5` or `claude-opus-5` is priced. See T-212.*
- [x] Cache-read and cache-write tokens are priced at their own rates, and a test proves an Anthropic-shaped response does not bill cached tokens again at the full input rate
- [x] The OpenAI-shaped branch is either removed (no OpenAI provider exists) or made correct — made correct by subtracting `cached_tokens` from `prompt_tokens` to prevent double-counting per OpenAI documentation
- [x] `usage_events` gains nullable `document_id`, `extraction_run_id` and `user_id`, with no foreign keys and indexes that lead with `tenant_id`; the record methods accept them
- [x] A test proves per-document cost is queryable, and that deleting the document through T-206 leaves the ledger untouched and does not raise
- [x] Full suite green and `ruff check .` clean

## Notes

The plan's field list for the ledger (ENTERPRISE_PLAN.md Stage 2) included a resource id and
a user id; T-207's acceptance list left them out, and an implementation that satisfied the
list inherited the omission. That is a defect in how the ticket was written.

Do this before T-210. A spend cap that reads a ledger recording half the real cost will let a
tenant spend twice its limit, and one that reads a ledger that raises will block ingestion.

# T-212 · Price the models the system actually routes to

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-212-price-the-models-we-route-to`

**Scope**
- `src/semanticgraph/control/usage/**`
- `tests/unit/control/**`
- `tests/integration/control/**`

**Blocked by** — · **Blocks** T-210 (the spend cap reads period spend from this ledger)

## Goal

T-211 made the ledger fail loudly, which was right, and it did not price the models the
plan uses. Checked by running the code on `main` at `4af6bd0`:

```
claude-haiku-4-5-20251001  -> UnpricedModelError
claude-sonnet-5            -> UnpricedModelError
claude-opus-5              -> UnpricedModelError
```

`PRICE_SCHEDULES` holds Claude 3.x models and generic family aliases, and the aliases carry
prices that do not match the current models:

| Alias in the table | Price in the table (in / out per M tokens) | Current model | Price on claude.com/pricing, read 2026-09-21 |
|---|---|---|---|
| `claude-opus` | $15 / $75 | Opus 5 | $5 / $25 |
| `claude-sonnet` | $3 / $15, or $2.50 / $12.50 in `2026-Q2` | Sonnet 5 | $2 / $10 |
| `claude-haiku` | $0.80 / $4, or $0.70 / $3.50 in `2026-Q2` | Haiku 4.5 | $1 / $5 |

The `2026-Q2` figures match nothing on the vendor page, and every entry cites a retrieval
date of 2026-03-01. Whatever the older numbers were, they are not the models this system
calls.

The test for this — "every routable model is priced" — checks the table against
`ROUTABLE_MODELS`, a hand-written set defined **in the same file, next to the table**. Change
both together and it passes for any table at all. It cannot notice that the model the gateway
really sends is missing.

Failing loudly is the right behaviour, and it means the first real model call raises. That
is what this ticket fixes.

## Acceptance

- [ ] Price keys are the **exact model ids as sent to the API** — at minimum `claude-haiku-4-5-20251001`, `claude-sonnet-5`, `claude-opus-5`, plus any other model the routing config can select and the embedding model in use. No prefix matching. If aliases are wanted they are an explicit mapping to one exact id, never a separate price
- [ ] Every price is read from the vendor's pricing page **on the day it is written**, with the URL and that date beside it. The values seen on 2026-09-21, for checking, were: Haiku 4.5 $1 / $5, cache read $0.10, cache write $1.25; Sonnet 5 $2 / $10, $0.20, $2.50; Opus 5 $5 / $25, $0.50, $6.25 (per million tokens, 5-minute cache TTL — record which TTL the code uses, since the 1-hour rate differs)
- [ ] The Claude 3.x models, the family aliases and the `2026-Q2` schedule are deleted, unless a saved copy of their source is kept beside them
- [ ] The set of routable models is **derived from the same configuration the gateway reads**, in one place, not listed separately. A test adds a model to that configuration without a price and **fails**, proving the check can fail
- [ ] A golden test for each of the three models prices a fixed token mix, including cache reads and writes, against a figure worked out by hand from the page's numbers
- [ ] Every retrieval date is the date the price was actually read, and never precedes the schedule's own period
- [ ] Full suite green and `ruff check .` clean

## Notes

Batch pricing (a 50% discount on these models) is deliberately left out: how ingestion uses
it is T-906's question, and the price schedule should gain a batch flag when that is decided,
not before.

Found reviewing T-211. Its acceptance list asked for the schedule to cover every model the
gateway can route to and for each price to be copied from the vendor page; both boxes were
ticked and neither was met, and that ticked box has been reverted with a pointer here.

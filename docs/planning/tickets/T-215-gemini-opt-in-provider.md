# T-215 · Add Gemini as an opt-in provider, for real-provider testing

**Stage** 3 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-215-gemini-provider`

**Scope**
- `src/semanticgraph/adapters/outbound/llm/**`
- `src/semanticgraph/control/usage/**`
- `src/semanticgraph/composition/model_routing.py`
- `.env.example`
- `tests/unit/adapters/**`
- `tests/unit/control/**`
- `tests/live/**`

**Blocked by** T-214, T-110 · **Blocks** —

## Goal

The plan is Anthropic-first, and **no real provider adapter exists yet** — `adapters/outbound/llm/`
is empty and the gateway is a test double. A Gemini key is available now, so Gemini can be the
first adapter behind `LLMGatewayPort` and validate the wiring, the usage accounting and the
extraction contract against a real model. It is **opt-in and does not replace** Anthropic or
OpenAI: the port stays provider-neutral and which provider is the default remains a decision.

This does not remove the need to evaluate local alternatives for air-gapped customers (T-904).

## What the primary sources say (read 2026-09-21)

**Terms** — [ai.google.dev/gemini-api/terms](https://ai.google.dev/gemini-api/terms). For *Unpaid
Services*, Google "uses the content you submit to the Services and any generated responses to
provide, improve, and develop Google products and services", human reviewers "may read, annotate,
and process your API input and output", and the terms say "Do not submit sensitive, confidential,
or personal information to the Unpaid Services." For *Paid Services*, Google "doesn't use your
prompts (including associated system instructions, cached content, and files such as images,
videos, or documents) or responses to improve our products", and retains logs briefly for abuse
detection only. **A free-tier key must never see customer text.**

**Usage fields** — [generateContent reference](https://ai.google.dev/api/generate-content).
`promptTokenCount` **includes** cached tokens ("this is still the total effective prompt size
meaning this includes the number of tokens in the cached content"); `cachedContentTokenCount` is
reported separately; `thoughtsTokenCount` is separate from `candidatesTokenCount`. Mapping
`promptTokenCount` straight onto `input_tokens` double-counts cached tokens — the same trap as
OpenAI's `prompt_tokens`, and the one T-211 fixed for OpenAI.

**Models and prices** — [pricing page](https://ai.google.dev/gemini-api/docs/pricing), last updated
2026-09-16. Exact ids include `gemini-2.5-flash-lite` ($0.10 / $0.40 per million tokens, batch half),
`gemini-2.5-flash` ($0.30 / $2.50), `gemini-3.5-flash-lite` ($0.30 / $2.50), `gemini-3.5-flash`
($1.50 / $9.00) and `gemini-3.1-pro-preview` ($2 / $12, no free tier). **`gemini-3.6-flash`,
`gemini-3.7-flash` and `gemini-3.8-flash` are $0.75 / $3.75 only "through 12/31/26", then
$1.50 / $7.50.** Free-tier rows are marked "Content used to improve our products".

**Structured output** — [docs](https://ai.google.dev/gemini-api/docs/structured-output). A supported
subset of JSON Schema (enums, `anyOf`, `required`, array bounds); "always validate values in your
application"; very large or deeply nested schemas "may be rejected"; and the page gives **no
guidance on field ordering or reasoning before the answer**, which the plan's extraction design
assumes for Claude.

## Acceptance

- [x] The key is read only from `GEMINI_API_KEY`. It appears in no source file, ticket, log, commit or test output; `.env` is already gitignored and `.env.example` carries a blank placeholder. A key that has ever been pasted into a chat or a log is rotated
- [x] `GEMINI_TIER` is `free` or `paid`, defaulting to `free`. The provider is registered only in dev and eval profiles by default; enabling it in a profile that handles customer tenants requires `paid`, and the container refuses to start otherwise. A test proves it
- [x] The adapter sits behind `LLMGatewayPort` and uses the same extraction contract as every provider — claim, verbatim quote, chunk id — with the quote located and verified by the application, never trusted from the model
- [x] Usage is normalised from a **real SDK response object**, not a dict: uncached input is `promptTokenCount − cachedContentTokenCount`, cache reads come from `cachedContentTokenCount`, and output includes `thoughtsTokenCount` **once the pricing documentation confirms thinking tokens are billed at the output rate** — that was not stated on the pages read, so confirm it before writing the rule. Unset fields are treated as 0
- [x] Prices are added as a **new price version**, not by editing the active one, since a published version is immutable (T-214). Each price has the exact model id, its source URL and the date it was read. The 2026-12-31 promotional cutoff is represented, so an event stamped after it cannot silently use the promotional rate
- [x] `ModelRouting` records Gemini as `hosted=True`, and the generated subprocessor list gains Google
- [x] A live smoke test under `tests/live/` runs only when `GEMINI_API_KEY` is present, uses only public or synthetic documents, and its absence is a visible skip with a reason. CI never depends on it
- [x] Fake-provider tests cover the adapter in CI: normal response, cached response, schema rejection, a fabricated quote that the locator rejects, and a timeout that yields *unverified* rather than a false result
- [x] No document text in logs, traces or error messages — ids and hashes only
- [x] Full suite green and `ruff check .` clean

## Notes

**A hypothesis, not a finding:** list prices per million tokens are Haiku 4.5 $1 / $5,
`gemini-3.5-flash-lite` $0.30 / $2.50 and `gemini-2.5-flash-lite` $0.10 / $0.40. If a Flash-Lite
model holds up against the T-904 gold labels with the quote-verification design, extraction
could cost several times less than the plan's $0.145 baseline. Nothing here shows it does.

Do this only after T-110: the extraction double there fixes the shape of the port a real adapter
must satisfy.

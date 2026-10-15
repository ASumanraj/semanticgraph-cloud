# T-229 · A dev-only open-model extractor for local demos (needs a decision)

**Stage** 3 · **Type** work · **Status** open · **Owner** — · **Branch** `t-229-dev-only-open-model-extractor`

**Scope**
- `src/semanticgraph/adapters/outbound/llm/**` (new adapter), `src/semanticgraph/composition/**`
- `src/semanticgraph/application/use_cases/ingest_document.py` (chunking only, if the decision below says so)
- `tests/unit/**`, `tests/integration/demo/**`, `.env.example`, `docs/research/**`

**Blocked by** [T-228](T-228-real-stack-demo-persistence-and-truthful-labelling.md) and the founder's decision below
· **Blocks** a demo that shows model extraction

## Decision (founder, 2026-10-15): option 1, build it guarded

Original decision text, kept for the record:

The founder has no Anthropic or Google billing, so the only model endpoint available is the free NVIDIA trial
endpoint. Its terms (read 2026-10) are evaluation only, not production, and inputs may be used to improve NVIDIA
models; no confidential or personal data. That makes it acceptable for a **local demo on public or synthetic text**
and unacceptable for any customer document. Options:

1. **Build it, guarded.** An adapter plus a guard like T-215's tier guard that refuses to start with a
   customer-facing profile unless an explicit `SEMANTICGRAPH_ALLOW_EVALUATION_ENDPOINT=1` is set, plus the banner from
   T-228 (`terms: "evaluation-only"`). Recommended if a real-extraction demo is wanted before there is paid access.
2. **Do not build it.** Wait for a paid provider key, and keep the demo on placeholder output with the honest banner.

## If option 1: what it does

- Adapter behind the existing LLM gateway port, reads only `NVIDIA_API_KEY` from the environment, never logs it, prices
  at an explicit zero entry in the ledger so usage is still recorded.
- Ontology limited to what the measurement supports (parties, agreement/effective/expiration dates, governing law,
  anti-assignment, termination for convenience, change of control). The demo must not show Cap On Liability,
  Non-Compete or Uncapped Liability as detected: the CUAD measurement found most such clauses missed (T-227).
- Chunking: the ingest chunker splits on blank lines with no size cap. Add a maximum chunk size on line boundaries
  before sending real text to a model, with a test that a text with no blank lines becomes several chunks.
- Every extracted entity keeps the verbatim quote and span; a quote that is not found in the chunk is dropped and
  counted, not shown.

## End-to-end checks

- [ ] Real model call on a **public or synthetic** contract only (a CUAD file, or a fixture written for the repo);
  rows in Postgres by SQL with spans that match the source; ledger row with model id and zero price.
- [ ] Guard test: with a customer-facing profile and no explicit allow flag, startup refuses.
- [ ] Banner shows the model id and the evaluation-terms line; placeholder entity names no longer appear.
- [ ] The key is absent from logs, traces, test output and the repository (a test greps captured logs).
- [ ] Call cap and rate limit (under 40 requests per minute) enforced and tested; a failing chunk is reported, not
  hidden.
- [ ] CI green without the key (the live test skips with a stated reason and is not counted as coverage).

# T-909 · CUAD-based clause-extraction eval harness

**Stage** 4 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-909-cuad-eval-harness`

**Scope**
- `evals/cuad/**`
- `tests/unit/evals/**`

**Blocked by** ~~a real Stage 3 extractor (not the T-110 deterministic double)~~ — resolved by
[T-215](T-215-gemini-opt-in-provider.md), which added a real Gemini adapter behind
`LLMGatewayPort`. Unblocked as of 2026-09-22. · **Blocks** —

## Goal

CUAD (Hendrycks et al., NeurIPS 2021, The Atticus Project, CC BY 4.0) is a free, independently
labelled set of 510 real commercial contracts across 41 clause categories, checked against the
T-904 manifest with zero overlap — see `docs/research/t904-cuad-crosscheck.md` for the licence
verification, the overlap check, and the category-to-question mapping this ticket builds from.

Do not start this before a real extractor exists. Running CUAD against today's deterministic
extraction double (T-110) would score a placeholder against real labels and report a meaningless
number.

## Design

Load `master_clauses.csv` and the matching contract texts, apply the mapping table in
`t904-cuad-crosscheck.md` §3, run the extractor, and score precision/recall per category for the
9 of 12 questions CUAD covers fully or partly (Q1–Q8, Q11, Q12). Do not attempt Q9 (cap
exclusions), Q10 (indemnity) or Q13 (amendment diff) against CUAD — it has no signal for any of
the three; those stay dependent on the T-904 paid-reviewer pass on our own documents.

## Acceptance

- [x] A dataset checksum is recorded before first use (§5 of the crosscheck report), not just an access date
- [x] CUAD is cited per its licence (Hendrycks et al., NeurIPS 2021, CC BY 4.0) wherever a score from it is reported
- [x] The harness reports precision/recall per CUAD category, not one blended number, so a weak category doesn't hide behind strong ones
- [x] No claim is made that a CUAD-based score says anything about temporal history, tenant isolation, resolution decisions or deletion — those aren't testable against CUAD by construction
- [x] Results state plainly that CUAD's contracts are likely present in model pretraining data, same caveat as the rest of T-904's corpus

## Notes

This is a second, free benchmark alongside T-904's own ten-document corpus, not a replacement for
it. T-904 stays the source of gold labels for the three questions CUAD can't answer.

Use `GeminiLLMGateway` (T-215) directly as the extractor — construct it from `GeminiConfig.from_env()`
in the harness script itself; this ticket's scope doesn't touch `composition/**`, so there's no need
to go through the app container. CUAD's contracts are public EDGAR filings, so the free tier's
"public or synthetic data only" constraint is satisfied without needing a paid key — but confirm
`GEMINI_TIER` before running at any volume, since the free tier's low rate limit will make 510
documents slow either way.

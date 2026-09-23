# T-909 · CUAD-based clause-extraction eval harness

**Stage** 4 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-909-cuad-eval-harness`

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

- [x] A dataset checksum is recorded before first use (§5 of the crosscheck report), not just an access date — independently verified against the real published file, see Review
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

## Review

Reviewed PR #12 (`cc6c493`) against `t-909-cuad-eval-harness`. Independently downloaded the real
`master_clauses.csv` from `theatticusproject/cuad` on HuggingFace and recomputed its SHA-256 myself
— `4da237bec677bf5b02212d523857cd57a801adde60e8021de063c8cc06823720`, 3,955,428 bytes — both match
`constants.py` exactly. The mapping table in `mapping.py` matches `t904-cuad-crosscheck.md` §3
faithfully: Q9/Q10 correctly `NOT_COVERED`, Q13 correctly `NOT_APPLICABLE`, the other 9 questions
mapped to the right CUAD categories. `metrics.py`'s per-category scoring has no blended aggregation,
as required. Ran the PR's own tests (7/7 passed) and the full suite (395 passed).

**Reopened for one defect, reproduced directly against the real dataset file (not a fixture):**
`loader.py`'s `parse_master_clauses_row` builds the answer-column key as `f"{cat}-Answer"` for every
category. That's right for 39 of CUAD's 40 non-identifier columns, but the real CSV's column for
one of Q5's two mapped categories is spelled with a space: `"Notice Period To Terminate
Renewal**- Answer**"`, not `"...Renewal-Answer"`. Confirmed by loading the real file and inspecting
`reader.fieldnames` directly — the no-space key genuinely does not exist in the header. Because
`row.get(f"{cat}-Answer", row.get(cat, ""))` evaluates its default eagerly, the lookup silently
falls back to the **base column** — which holds the full verbatim source-span sentence, not the
short normalized answer:

```
Notice Period To Terminate Renewal          -> "['This Agreement may be terminated by either
                                                 party at the expiration of its term or any
                                                 renewal term upon thirty (30) days written
                                                 notice to the other party.']"
Notice Period To Terminate Renewal- Answer  -> "30 days"
```

So the ground truth loaded for this one category is a full sentence (with Python list-repr
brackets `parse_cuad_answers` doesn't know to strip, since it only strips leading/trailing `'`/`"`),
not "30 days" — any model correctly extracting "30 days" would score as a false positive/false
negative pair against wrong ground truth for this category, dragging down Q5's partial-fit score
for a reason that has nothing to do with the model. Checked all 40 other category columns against
the real header: this is the only one with the inconsistent naming, so the blast radius is exactly
this one category (`Notice Period To Terminate Renewal`, half of Q5), not systemic. Zero test
coverage of this: `test_cuad_harness.py` has no reference to "Notice Period" or "Renewal" anywhere.

**Fix direction:** `parse_master_clauses_row` needs a per-category answer-column override (a small
dict mapping `"Notice Period To Terminate Renewal"` to its real, space-containing column name), or a
more defensive lookup that tries both `f"{cat}-Answer"` and `f"{cat}- Answer"` before falling back to
the base column. Add a test that loads a fixture row shaped exactly like the real CSV's header
(including the space) and asserts the parsed answer is the short form, not the source span — the
case the current suite has no coverage for at all.

Continue on the same branch or a new one off `main`, agent's choice — this is a one-file, one-method
fix with no migration or scope conflict.

## Review, fix verified 2026-09-23

Reviewed PR #12 (`2c8d7fc`) against `t-909-cuad-eval-harness`. `loader.py` now carries a
`CATEGORY_ANSWER_COLUMN_OVERRIDES` map (`"Notice Period To Terminate Renewal"` →
`"Notice Period To Terminate Renewal- Answer"`) and `get_answer_column_candidates()`, which checks
the override first, then `-Answer`/`- Answer`/` - Answer`/` Answer` suffixes, before ever falling
back to the base column.

Independently re-verified against the real downloaded `master_clauses.csv` (not the fixture):
confirmed `"Notice Period To Terminate Renewal- Answer"` is present in the real header and the
no-space variant is not, then ran the actual first data row through the fixed
`parse_master_clauses_row` myself — it now returns `["30 days"]` instead of the source-span
sentence. Also spot-checked several unrelated categories (`Agreement Date`, `Anti-Assignment`,
`Cap On Liability`, `Change Of Control`) through the same row to confirm the override map didn't
regress the other 39 categories' normal `-Answer` lookup.

The new unit test (`test_loader_handles_notice_period_column_space_inconsistency`) is a real test,
not a rubber stamp — its fixture includes both the wrong base column and the real answer column
side by side, so it actually proves the override wins rather than passing by omission.

Ran the suite myself: `pytest tests/unit/evals/test_cuad_harness.py -q` → 8 passed. `ruff check
evals/cuad tests/unit/evals` → clean. Full suite → 347 passed, 50 skipped, 2 deselected — matches
the PR's own numbers exactly. Accepted. Status set to done.

# T-904 pilot corpus — 10 EDGAR contracts + 3 predecessors

Ten real, publicly filed SEC EDGAR exhibits from ten different companies, chosen for the
wave-1 labelling pilot (see `docs/research/t904-pilot-document-selection.md` for why each one
was picked, and `docs/research/t904-pilot-labelling-guide.md` for how to label them). Three are
amendments or restatements; each has its predecessor agreement downloaded alongside it.

## What this is, and is not

This is a reproducible **engineering benchmark**, not a blind evaluation set. These are public
filings and are very likely present in the pretraining data of the models we route to (an
inference, not a checked fact) — results measured here must be reported as such. Only a design
partner's own, unseen documents test the pipeline on genuinely novel text.

## Files

- `manifest.csv` — one row per document: id, company, CIK, form, filing date, exhibit number,
  source URL, local filename, **sha256 computed from the committed bytes**, size, licence, track,
  split, the predecessor it amends (if any), an estimated page count, and its redaction level.
- `documents/` — the ten pilot documents.
- `predecessors/` — the three original or prior-restatement agreements the amendment rows amend.
- `_download_log.csv`, `_predecessor_log.csv` — the raw download log, kept for the record (see
  "Checksum note" below).

## Licence

Read from sec.gov directly, not a summary: EDGAR filings are U.S. federal government public
record. The SEC states "Anyone can access and download this information for free," and its
privacy notice states the information "may be copied or further distributed by users of the web
site without the SEC's permission." There is no click-through licence. The only real constraint
is operational: a declared `User-Agent` and a courteous request rate, both of which the fetch
here used (`SemanticGraph Cloud research (support@myschoolone.com)`, ≥0.6s between requests).

## Splits (by company, never by document)

| Split | Companies |
|---|---|
| development | Altiris/Dell, Portal Software, Unified Western Grocers, Strategic Diagnostics, Elite Pharmaceuticals (+ predecessor), Alarm.com (+ predecessor) |
| validation | Cerus (+ predecessor), Escalade |
| sealed_holdout | Washington Gas Light, Synacor |

A predecessor document always carries its amendment's split, so no company's contract family
spans two splits — enforced by `tests/unit/evals/test_edgar_manifest.py`.

## Redaction

Two documents (Cerus, row 07; Synacor, row 10) and one predecessor (Elite's original, row
05_pred) carry `[*]`-style confidential-treatment redactions, concentrated in pricing, volumes
and insurance limits. Do not write a gold label whose answer is a redacted value.

## Checksum note

The selection research (`t904-pilot-document-selection.md`) reported different sha256 values for
six of these ten documents and all three predecessors — every `.htm` file, never a `.txt` one —
each off by exactly 6 bytes. I re-downloaded every file directly from sec.gov with `curl` before
committing them, confirmed each is well-formed (opens with `<DOCUMENT>`, closes with
`</DOCUMENT>`, the tag structure inside is intact) and used **the sha256 of the bytes actually
committed here** as the manifest's value — that is what
`test_every_document_hash_matches_the_file_on_disk` checks, and it is the only checksum that
matters going forward. The 6-byte discrepancy itself is unexplained (not a truncation — nothing
is cut off — and not a CRLF/LF difference; the files contain no `\r`) and is not worth more time
to chase, but recording it here means nobody re-derives a "correct" hash from the older report by
mistake.

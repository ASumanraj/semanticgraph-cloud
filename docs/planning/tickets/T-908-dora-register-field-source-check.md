# T-908 · Check whether the DORA register is actually built from contracts

**Stage** — · **Type** research · **Status** done · **Owner** — · **Branch** `t-908-dora-register-check`

**Scope**
- `docs/research/**`

**Blocked by** — · **Blocks** any interview with S3 (see T-907)

## Question

T-907 found one externally measured failure in the whole market: the ESAs' 2024 dry run, where
6.5% of registers of information passed every data-quality check, 86% of errors were missing
mandatory information, and improper identifiers came next. That makes the register the strongest
candidate for customer one.

It does not show that the missing fields live in *contracts*. Many register fields come from
procurement systems, vendor masters or internal assessments. If most of them do, a contract
knowledge product addresses a small part of the problem, and ten interviews would be spent finding
that out.

## Resolution

Done 2026-09-21. Report: `docs/research/dora-register-field-source.md`. Contract-derived share about
14% against the one-third threshold set beforehand, so the DORA-register segment is dropped as customer
one. No 2025 or 2026 pass rate is published. Regulation text read from the Official Journal PDFs.

Method, as planned. Two checks, both free and neither needing an interview:

1. **Classify every mandatory data point** in the ESAs' published register data-point model by where
   its value comes from: **contract text**, **a system of record**, or **an internal assessment**.
   Read the regulation's own text and technical standards for each field rather than inferring from
   its name. Report the share in each class. **Set the threshold before counting:** if fewer than
   about a third of mandatory fields are contract-derived, the contract-knowledge case for this
   segment is small.
2. **Find the ESAs' or the national authorities' feedback on the 2025 and 2026 submissions** and
   record the aggregate pass rate. If it has recovered above about 70%, the window has closed.

Also read the regulation text on EUR-Lex directly. The research pass could not open it, so every
statement in T-907 about Article 28(3) and Article 30, including whether an ICT service provider to a
financial entity becomes an entry in that entity's register, is unverified.

Record findings as a short report and update the customer-one hypothesis in
`docs/research/contract-ai-market-and-customer-one.md` either way.

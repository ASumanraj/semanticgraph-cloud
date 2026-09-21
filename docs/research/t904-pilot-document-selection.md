# T-904 — Pilot document selection (10 EDGAR contracts for wave-1 labelling)

**Status** research input to T-904, wave 1 · **Date** 2026-09-22 · **Branch** `docs/plan-corrections`

Ten real, publicly filed contracts from SEC EDGAR, chosen so that a *non-lawyer* labeller
(product owner, friends — **draft** labels, never gold) can work through one in a sitting.
Selection rules applied: ten different companies, no shared contract family, EX-10 exhibits,
short-to-medium length, employment and credit agreements excluded, at least three amendments
or amended-and-restated agreements whose predecessor is also on EDGAR.

Every URL below was fetched and the body read. Clause presence was verified by searching the
extracted text; anything not found in the text is written **not seen**, not guessed.
Page counts are estimates (extracted words ÷ 450) — EDGAR exhibits are HTML/ASCII with no
pagination, so treat them as ±20%.

## Source licence and terms (read from sec.gov, not a summary)

The SEC states on its own pages that EDGAR filings are public: "Anyone can access and download
this information for free," and its privacy notice states that "Information presented on sec.gov
is considered public information and may be copied or further distributed by users of the web
site without the SEC's permission." There is no click-through licence and no attribution
requirement; the constraint the SEC does impose is operational rather than legal — automated
retrieval must "declare your user agent in request headers," is capped at a "Current max request
rate: 10 requests/second," and the SEC "reserves the right to limit request rates to preserve
fair access for all users," asking users to "Download only what you need and please moderate
requests to minimize server load." It also blocks unidentified bots. So for the corpus manifest
the licence field is *US federal government public record, no redistribution restriction*, and
the obligation that actually binds us is the fetcher's `User-Agent` and rate limit — which the
fetch script used here honoured (identified UA, ≥0.6 s between requests).

Sources: [Accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) ·
[SEC privacy information](https://www.sec.gov/about/privacy-information)

## Split-by-company rule

No two rows share a company, a counterparty, or a contract family. Strategic Diagnostics'
2009 amended-and-restated DuPont Qualicon distribution agreement was deliberately **excluded**
because its predecessor chain overlaps row 4's 2005 agreement — one SDI family, one row.
Cerus appears once (the Ash Stevens supply family); its separate Porex family was not used.
When Track C is split 6 / 2 / 2, the split must be taken over these ten companies, and the
"original" documents listed in the amendment rows inherit their amendment's split.

## The ten

### 1 · Altiris, Inc. — Software License Agreement with Dell
- **CIK** 0001139650 · **Form** 10-K, filed 2003-03-28 · **Exhibit** EX-10.7
- **URL** https://www.sec.gov/Archives/edgar/data/1139650/000102140803005194/dex107.txt
- **Type / industry** software licence + distribution / systems-management software
- **Pages** ~39 · **Amendment** no
- **sha256** `90349b6051b8945b458437669ef4e0e29d076b05711d991f3daf3beaab6ac261` · 131,944 bytes
- **Why** The richest plain-shape licence in the set and a genuine two-party negotiated deal
  (Altiris licensing to Dell Products L.P.), with the whole clause spine visible in ordinary
  English. Attaches an end-user licence form and a source-code escrow agreement, so it also
  exercises multi-document-in-one-exhibit chunking.
- **Clauses** parties ✓ · effective date ✓ · term ✓ · renewal ✓ · termination for convenience ✓
  ("Either Party may terminate this Agreement without cause upon 180 days prior written notice")
  · governing law ✓ (New York; the attached end-user form says Utah — a deliberate trap worth
  labelling) · liability cap ✓ ("THE AGGREGATE LIABILITY OF ALTIRIS … SHALL NOT EXCEED THE AMOUNT
  OF ALL LICENSE FEES PAID") · exclusions from the cap **not seen** · indemnification ✓ ·
  assignment/change of control **not seen** · exclusivity ✓
- **Redaction** ~35 asterisk markers, mostly in pricing exhibits; the operative clauses are intact.

### 2 · Portal Software, Inc. — Form of Software License Agreement
- **CIK** 0001080306 · **Form** 10-K, filed 2002-03-25 · **Exhibit** EX-10.16
- **URL** https://www.sec.gov/Archives/edgar/data/1080306/000101287002001436/dex1016.txt
- **Type / industry** software licence / telecom billing software
- **Pages** ~16 · **Amendment** no
- **sha256** `ba57758f25c77567faa4525969b5a596e2e22adb0323eb39c3cbbcc0abe72c37` · 51,446 bytes
- **Why** The cleanest "textbook" licence: short, unredacted, and it has the exact pattern the
  flagship demo question needs — a cap **with named carve-outs**. Filed as a *form of* agreement,
  so the commercial schedule has blanks; that is itself a useful negative case for the extractor.
- **Clauses** parties ✓ · effective date ✓ · term ✓ (perpetual / per-schedule) · renewal ✓ ·
  termination for convenience **not seen** · governing law ✓ (California) · liability cap ✓
  ("NEITHER PARTY'S … LIABILITY FOR ANY DAMAGES SHALL EXCEED AN AMOUNT EQUAL TO THE TOTAL FEES
  PAID AND OWED TO PORTAL") · exclusions from the cap ✓ (Sections 14 infringement indemnity and
  17 confidentiality carved out) · indemnification ✓ · assignment/change of control **not seen** ·
  exclusivity ✓
- **Redaction** none.

### 3 · Unified Western Grocers, Inc. — Supply Agreement with C & K Market
- **CIK** 0000320431 · **Form** 10-Q, filed 2004-02-10 · **Exhibit** EX-10.62
- **URL** https://www.sec.gov/Archives/edgar/data/320431/000119312504018389/dex1062.htm
- **Type / industry** supply / grocery wholesale distribution
- **Pages** ~13 · **Amendment** no
- **sha256** `cec4022949d6d41365675bdcd8fa43388b4496db5d80cd656388fcb407498a2d` · 91,388 bytes
- **Why** Short, entirely unredacted, and a non-tech industry so the corpus is not all software.
  Has a break-up fee tied to early termination, which is a fee obligation the current free-string
  `Obligation.obligation_type` cannot model — good evidence for the clause-type shortlist.
- **Clauses** parties ✓ · effective date ✓ (29 Dec 2003) · term ✓ · auto-renewal **not seen** ·
  termination for convenience **not seen** · governing law ✓ (California) · liability cap
  **not seen** · exclusions **not seen** · indemnification **not seen** · assignment/change of
  control ✓ · exclusivity **not seen**
- **Redaction** none.

### 4 · Strategic Diagnostics Inc. — Exclusive Distribution and Supply Agreement with DuPont Qualicon
- **CIK** 0000911649 · **Form** 10-Q, filed 2005-08-15 · **Exhibit** EX-10.1
- **URL** https://www.sec.gov/Archives/edgar/data/911649/000095011605002781/ex10-1.txt
- **Type / industry** exclusive distribution + supply / life-science diagnostics
- **Pages** ~22 · **Amendment** no
- **sha256** `84101346f742796895823fc65f129a8e51bc806e395f473b9e5e0b8a1f411fbf` · 67,520 bytes
- **Why** An unredacted exclusivity agreement with an explicit renewal ladder ("renew for five (5)
  additional periods of one (1) Calendar Year each"), which is the shape that makes the
  auto-renewal question non-trivial. Plain ASCII, so it is also the natural Track D scan source.
- **Clauses** parties ✓ · effective date ✓ · term ✓ · renewal ✓ · termination for convenience
  **not seen** · governing law ✓ (Delaware) · liability cap **not seen** (there is a mutual
  indemnity and a limitation-on-actions clause, but no monetary cap) · exclusions **not seen** ·
  indemnification ✓ · assignment/change of control ✓ · exclusivity ✓
- **Redaction** none.

### 5 · Elite Pharmaceuticals, Inc. — First Amendment to the TPN–Elite Manufacturing and Supply Agreement **[AMENDMENT]**
- **CIK** 0001053369 · **Form** 10-Q, filed 2016-11-17 · **Exhibit** EX-10.6
- **URL** https://www.sec.gov/Archives/edgar/data/1053369/000114420416135163/v453381_ex10-6.htm
- **Original** Manufacturing and Supply Agreement dated 23 June 2011, EX-10.71 to the 10-K filed
  2011-06-29 — https://www.sec.gov/Archives/edgar/data/1053369/000114420411038267/v227306_ex10-71.htm
  (~19 pages, sha256 `ff3d20e29ac8903236cd2bba49e1a087ff2f11dd07758afd8f833ce143160584`, 155,941 bytes;
  governing law New Jersey; indemnification and renewal present; ~25 asterisk redactions in pricing)
- **Type / industry** manufacturing & supply amendment / generic pharmaceuticals
- **Pages** ~2 · **Amendment** yes
- **sha256** `586a9d91b2700a629deccda4fc0bb5d7f39da9f2c1b7a3b909ca2e4dde59ca01` · 20,895 bytes
- **Why** The cleanest "what did the amendment change" test in the set: a short letter amendment
  that names its parent by title and date, changes term and exclusivity, and is unredacted, while
  the full parent is one URL away. Cheap to label, high diagnostic value.
- **Clauses** parties **not seen** as a formal preamble (addressed as a letter) · effective date ✓ ·
  term ✓ · renewal ✓ · termination for convenience **not seen** · governing law **not seen**
  (inherited from the parent — itself a good labelling question) · liability cap **not seen** ·
  exclusions **not seen** · indemnification **not seen** · assignment **not seen** · exclusivity ✓
- **Redaction** none in the amendment.

### 6 · Alarm.com Holdings, Inc. — Fourth Amendment to Deed of Office Lease Agreement **[AMENDMENT]**
- **CIK** 0001459200 · **Form** 10-Q, filed 2016-11-14 · **Exhibit** EX-10.3
- **URL** https://www.sec.gov/Archives/edgar/data/1459200/000145920016000050/a103fourthamendmenttolease.htm
- **Original** Deed of Office Lease Agreement (Marshall Property LLC / Alarm.com), EX-10.2 to the
  S-1 filed 2015-05-22 —
  https://www.sec.gov/Archives/edgar/data/1459200/000119312515198768/d723141dex102.htm
  (~103 pages, sha256 `bc1190077a1f586db42ab8aa8af98961ff5689504e83f656af64a54c92335178`, 479,950 bytes;
  governing law Virginia, liability cap, assignment/change-of-control, indemnity all present)
- **Type / industry** commercial real-property lease amendment / connected-home software tenant
- **Pages** ~3 · **Amendment** yes
- **sha256** `65b05669e8f5cb7b2d23cfb240b7fa3489b66e60efdfb58a15c4f2e9e5eb4a3f` · 31,478 bytes
- **Why** A different document genus (lease, not commercial services) and a long amendment chain —
  Alarm.com has filed at least fifteen amendments to the same lease, so this row extends naturally
  into a cross-document entity-resolution and "current state of the agreement" test later.
- **Clauses** parties ✓ · effective date ✓ (15 Sept 2016) · term ✓ (extends the term) · auto-renewal
  **not seen** · termination for convenience **not seen** · governing law ✓ (Virginia) · liability
  cap **not seen** · exclusions **not seen** · indemnification ✓ · assignment **not seen** ·
  exclusivity **not seen**
- **Redaction** none.

### 7 · Cerus Corporation — Amended and Restated Supply Agreement with Ash Stevens Inc. **[A&R]**
- **CIK** 0001020214 · **Form** 10-K, filed 2024-03-05 · **Exhibit** EX-10.6
- **URL** https://www.sec.gov/Archives/edgar/data/1020214/000095017024026195/cers-ex10_6.htm
- **Predecessor on EDGAR** Amended and Restated Supply Agreement (same parties), EX-10.1 to the
  10-Q filed 2011-11-03 —
  https://www.sec.gov/Archives/edgar/data/1020214/000119312511295406/d236182dex101.htm
  (~19 pages, sha256 `c539e1d13cb94cb7cc5c9f46dcb4dfd00e9369c7b758e75ab6f9b48afc473d9c`, 122,523 bytes;
  governing law Michigan; ~96 bracketed redactions). The document restates an original of
  14 November 2002, which predates full-text search coverage and was **not located** on EDGAR —
  the 2011 restatement is the usable predecessor.
- **Type / industry** supply / medical devices, blood-safety (contract API manufacture)
- **Pages** ~11 · **Amendment** yes (amends and restates)
- **sha256** `73a2befee9a1fdaa167c7675b22aa1e69fcd984f8c88165b622c1b6b66e77558` · 134,340 bytes
- **Why** The only true restatement-vs-restatement pair in the set: two full texts of the same
  agreement twelve years apart, which is exactly the diff the "what changed" question needs, and
  short enough to label both. Has an explicit automatic-extension mechanic with a notice-of-
  termination cut-off.
- **Clauses** parties ✓ · effective date ✓ · term ✓ · auto-renewal ✓ ("Automatic Extension
  Period(s) … unless either Party provides the above-described Notice of Termination") ·
  termination for convenience ✓ (notice-based) · governing law ✓ (Michigan) · liability cap
  **not seen** (insurance minimums instead, and those amounts are redacted) · exclusions
  **not seen** · indemnification ✓ · assignment **not seen** · exclusivity **not seen**
- **Redaction** ⚠ ~43 `[ * ]` markers — pricing, volumes and insurance limits are removed.
  Do not write questions whose answer is a number in this document.

### 8 · Washington Gas Light Company — Master Services Agreement
- **CIK** 0000104819 · **Form** 10-K, filed 2011-11-23 · **Exhibit** EX-10.1
- **URL** https://www.sec.gov/Archives/edgar/data/104819/000119312511321368/d258211dex101.htm
- **Type / industry** master services (outsourcing, SOW-based) / regulated gas utility
- **Pages** ~62 · **Amendment** no
- **sha256** `520fbc18fb3edcefce685503f0db613ab613c1373e0585205903d8e96f4d6e5b` · 384,832 bytes
- **Why** The only long, fully unredacted MSA found. It is the master-plus-Statements-of-Work
  shape the product actually targets, and it is where term lives at the SOW level rather than the
  master — the case that breaks naive term extraction. **At the length cap**: ~62 estimated pages
  against a ~60 ceiling. If the reviewer-hour budget is tight, this is the first row to swap.
- **Clauses** parties ✓ · effective date ✓ · master term ✓ (per-SOW; a single master expiry is
  **not seen**) · renewal ✓ (SOW renewal terms) · termination for convenience ✓ · governing law ✓
  ("LAWS OF THE COMMONWEALTH OF VIRGINIA EXCLUDING ITS CONFLICTS") · liability cap — a monetary
  aggregate cap was **not seen**; there is a "not exceed the sale price" limit on a specific
  remedy · exclusions from the cap ✓ · indemnification ✓ · assignment/change of control ✓ ·
  exclusivity **not seen** (there is a one-year non-solicitation of employees, which is a
  different clause type and worth its own label)
- **Redaction** none.

### 9 · Escalade, Incorporated — Services Agreement
- **CIK** 0000033488 · **Form** 10-Q, filed 2003-10-24 · **Exhibit** EX-10.7
- **URL** https://www.sec.gov/Archives/edgar/data/33488/000095015203009048/l03724aexv10w7.txt
- **Type / industry** services / sporting-goods and office-products manufacturing
- **Pages** ~7 · **Amendment** no
- **sha256** `380b75cd4219fa971af127089f3e7e82ea1a03adfb4971cc54018725515c5d6a` · 22,562 bytes
- **Why** The shortest full agreement in the set and completely unredacted — the right document to
  warm a new labeller up on before handing them row 1 or row 8. Plain ASCII, no tables.
- **Clauses** parties ✓ (three parties, including Indian Industries) · effective date ✓
  (5 Sept 2003) · term **not seen** as a fixed expiry · auto-renewal **not seen** · termination
  for convenience ✓ · governing law ✓ (Indiana) · liability cap **not seen** · exclusions
  **not seen** · indemnification ✓ · assignment ✓ · exclusivity **not seen**
- **Redaction** none.

### 10 · Synacor, Inc. — Master Services Agreement with Embarq Management Company
- **CIK** 0001408278 · **Form** S-1/A, filed 2012-02-01 · **Exhibit** EX-10.11.1
- **URL** https://www.sec.gov/Archives/edgar/data/1408278/000119312512034176/d253349dex10111.htm
- **Type / industry** master services / internet portal services to a telecom carrier
- **Pages** ~30 · **Amendment** no
- **sha256** `4901dc0b63d11e6f63f8404ce61b8e35f9755d4c6ae48ee5cc4e53ebbb836264` · 307,565 bytes
- **Why** The densest clause mix at a manageable length: term, renewal, an aggregate cap *and*
  carve-outs from it, indemnity, assignment and change of control all present in one 30-page
  document. This is the row that most directly answers "which agreements have uncapped liability
  and auto-renewal?".
- **Clauses** parties ✓ · effective date ✓ · term ✓ · auto-renewal ✓ · termination for
  convenience **not seen** · governing law ✓ (Delaware) · liability cap ✓ · exclusions from the
  cap ✓ · indemnification ✓ · assignment/change of control ✓ · exclusivity **not seen**
- **Redaction** ⚠ ~18 `[*]` markers under a confidential-treatment request, concentrated in fees
  and service levels. The liability and term clauses read intact.

## Proposed double-labelled overlap set (3 of 10)

For the 30-question agreement figure in the wave-1 protocol, double-label:

1. **Row 10, Synacor / Embarq MSA** — the widest clause coverage in the set, including the
   cap-plus-carve-out pattern that the agreement figure most needs to be measured on.
2. **Row 1, Altiris / Dell Software License Agreement** — a cap, a for-convenience termination
   with a 180-day notice, and two conflicting governing-law clauses in one exhibit. Disagreement
   here is informative rather than noise.
3. **Row 7, Cerus / Ash Stevens A&R Supply Agreement** — the amendment in the overlap set, as
   required. Its automatic-extension-with-notice mechanic is the clause type reviewers are most
   likely to read differently, and its restated predecessor is available for the diff question.

Rows 1 and 10 are the two "plain, common shapes" the question set was written against, so the
overlap also doubles as a sanity check that the question set transfers between documents.

## Flags

- **Scanned / image exhibits** — none in the ten. One candidate was rejected for this: NuScale
  Power's Doosan MSA (EX-10.26, 10-K 2024-03-15,
  `.../data/1822966/000182296624000039/ex1026doosanmsa-redacted.htm`) extracts as OCR garble
  ("• ! NUSCALE\" \" Powe , lo, c, 11 l 1u,n □ n k;n d"). It is worth keeping as a **Track D**
  real-scan specimen, and it is evidence against the plan's claim that "official filings are HTML
  or ASCII" — a filer can and does post an image-only exhibit.
- **Heavy redaction** — rows 7 (Cerus, ~43 `[ * ]`) and 10 (Synacor, ~18 `[*]`) plus the Elite
  *original* (~25). Rejected for redaction too heavy to label: PTC/Rockwell reseller agreement
  (~288 markers), Broadridge/Penson MSA (~240), Universal Biosensors distribution agreement (~207).
- **Length** — row 8 is at the ceiling (~62 estimated pages); rows 5, 6 and 9 are under the
  8-page preference (~2, ~3, ~7). That is unavoidable for amendments, which are short by nature,
  and it keeps the ten inside the 40-hour reviewer cap.
- **Provenance note for the manifest** — row 2 is a *form of* agreement (blanks in the commercial
  schedule) rather than an executed contract. Record that in the manifest; it changes what a gold
  label for "contract value" or "effective date" can mean.

## Content hashes

All thirteen files (the ten pilot documents plus the three predecessor agreements) were
downloaded successfully with an identifying `User-Agent` and ≥0.6 s between requests, into a
scratchpad directory outside the repository. sha256 and byte size are recorded inline above.
No document failed to download.

## Method

EDGAR full-text search (`efts.sec.gov/LATEST/search-index`) was queried for body phrases
("This Supply Agreement", "This Software License Agreement is entered into", "Amendment No. 1 to
the Master Services Agreement" …) rather than exhibit titles, then each hit was fetched, stripped
of markup, and scanned with clause-specific regular expressions; every ✓ and every **not seen**
above reflects that scan plus a read of the surrounding text. Full-text search only covers filings
from 2001 onward, which is why one predecessor (Cerus, 2002) could not be located.

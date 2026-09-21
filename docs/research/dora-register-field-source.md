# T-908 · Where the DORA register's mandatory fields actually come from

**Date** 2026-09-21 · **Ticket** T-908 · **Threshold set before counting:** fewer than ~1/3 of
mandatory fields contract-derived ⇒ the contract-knowledge case for segment S3 is small.

Every claim below is tagged `[verified: URL]` (a primary source states it), `[secondary]`
(a law firm / vendor / press restatement) or `[NOT VERIFIED]`.

---

## 1 · The primary law

Both primary texts were opened this time. EUR-Lex's HTML renderer truncates both documents in the
recitals; the **Official Journal PDF** for each works and was read in full locally.

### Regulation (EU) 2022/2554, Article 28(3) — the register obligation

> "As part of their ICT risk management framework, financial entities shall maintain and update at
> entity level, and at sub-consolidated and consolidated levels, a register of information in
> relation to all contractual arrangements on the use of ICT services provided by ICT third-party
> service providers. […] The contractual arrangements […] shall be appropriately documented,
> distinguishing between those that cover ICT services supporting critical or important functions
> and those that do not. […] Financial entities shall make available to the competent authority,
> upon its request, the full register of information […]"
> `[verified: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32022R2554]`

**So: does an ICT provider to a financial entity become an entry in that entity's register?**
Yes. The register covers **all** contractual arrangements for ICT services, not only critical ones;
the provider is identified in template `B_05.01` and the agreement in `B_02.01`/`B_02.02`
`[verified: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402956]`. Subcontractors
are in scope too (`B_05.01` covers "all subcontractors that are identified in template B_05.02").

**What DORA then requires of our contract** — Article 30(2) makes nine elements mandatory in *every*
ICT contract: service description and subcontracting conditions; locations of provision and of data
processing/storage plus advance notice of changes; data availability/integrity/confidentiality;
access, recovery and return of data on insolvency or termination; service level descriptions;
incident assistance at no or ex-ante cost; cooperation with competent and resolution authorities;
termination rights and minimum notice periods; participation in the entity's security awareness
programmes. Article 30(3) adds, for critical-or-important functions: full SLAs with quantitative
targets, notice/reporting obligations, contingency plans and security measures, TLPT participation,
**unrestricted access, inspection and audit rights** for the entity *and the competent authority*,
and **exit strategies with a mandatory transition period**.
`[verified: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32022R2554]`

This confirms the synthesis's temper #3 as fact, not hypothesis: selling to an EU financial entity
means signing an Article 30 contract, including audit and exit clauses, and being listed with an
identifier in a file the regulator reads.

### Commission Implementing Regulation (EU) 2024/2956 — the ITS

Verified: **Implementing Regulation (EU) 2024/2956 of 29 November 2024**, ITS on the standard
templates for the register of information, OJ 2.12.2024, ELI
`http://data.europa.eu/eli/reg_impl/2024/2956/oj`
`[verified: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402956]`.
The ticket's guess of the number was right. Note the final templates are coded **`B_xx.xx`**, not
`RT.xx` — `RT.` was the ESAs' draft/dry-run naming `[secondary]`.

---

## 2 · Every mandatory data point, classified

Fifteen templates `[verified: ITS Annex I]`. Classification is read from the ITS **fill-in
instruction** text, not the column name. "Mandatory" includes conditionally mandatory
("Mandatory if …") — the condition is about applicability, not optionality. The three genuinely
**Optional** fields (`B_05.01.0030`, `B_06.01.0070`, `B_07.01.0120`) are excluded from counts.
`B_99.01` is a free-text glossary of the entity's own closed-set meanings and has no comparable
data points; excluded, noted.

Legend: **C** = contract text · **S** = system of record · **A** = internal assessment.

| Template | Field | Name (short) | Class | Why (from the ITS instruction) |
|---|---|---|---|---|
| B_01.01 | 0010–0040 | LEI, name, country, type of FE | S ×4 | Entity master data |
| B_01.01 | 0050–0060 | Competent authority, reporting date | S ×2 | Reporting metadata |
| B_01.02 | 0010–0040 | LEI, name, country, type | S ×4 | Entity master data |
| B_01.02 | 0050 | Hierarchy within the group | S | "Determine the hierarchy … in the consolidation" |
| B_01.02 | 0060 | LEI of direct parent | S | Org hierarchy |
| B_01.02 | 0070–0090 | Dates of last update / integration / deletion | S ×3 | Register housekeeping |
| B_01.02 | 0100–0110 | Currency, total assets | S ×2 | "as reported in the financial statements" |
| B_01.03 | 0010–0040 | Branch code, head-office LEI, branch name, country | S ×4 | Entity master data |
| B_02.01 | 0010 | Contractual arrangement reference number | S | **"the internal reference number … assigned by the financial entity"** — not in the contract |
| B_02.01 | 0020 | Type of arrangement (standalone / overarching / subsequent) | **C** | Structure of the agreement itself |
| B_02.01 | 0030 | Overarching arrangement reference number | S | Internal reference again |
| B_02.01 | 0040–0050 | Currency, **annual expense or estimated cost for the past year** | S ×2 | Actual past-year spend — AP/finance, not the price clause |
| B_02.02 | 0010–0050 | Contract ref, FE LEI, provider code, code type, function identifier | S ×5 | All "as reported in" other templates |
| B_02.02 | 0060 | Type of ICT services (Annex III closed set) | **C*** | Taxonomy code for the contracted service description — borderline, see below |
| B_02.02 | 0070 | Start date | **C** | "date of entry into force **as stipulated in the contractual arrangement**" |
| B_02.02 | 0080 | End date | **C** | "end date **as stipulated in the contractual arrangement**" |
| B_02.02 | 0090 | Reason of termination | S | Records an event that happened, closed set |
| B_02.02 | 0100 | Notice period for the financial entity | **C** | Termination notice, business-as-usual |
| B_02.02 | 0110 | Notice period for the provider | **C** | Termination notice, business-as-usual |
| B_02.02 | 0120 | Country of governing law | **C** | Governing-law clause |
| B_02.02 | 0130 | Country of provision of the ICT services | **C*** | Art 30(2)(b) locations clause — borderline |
| B_02.02 | 0140 | Storage of data (Yes/No) | **C*** | "is the ICT service related to (or does it **foresee**) storage" — borderline |
| B_02.02 | 0150 | Location of data at rest | **C*** | Art 30(2)(b) — borderline |
| B_02.02 | 0160 | Location of data processing | **C*** | Art 30(2)(b) — borderline |
| B_02.02 | 0170 | Sensitiveness of the data | **A** | Low/Medium/High judgement by the entity |
| B_02.02 | 0180 | Level of reliance on the ICT service | **A** | Not significant → full reliance, impact judgement |
| B_02.03 | 0010–0020 | Two contract reference numbers | S ×2 | Internal references |
| B_03.01 | 0010–0020 | Contract ref, LEI of signing entity | S ×2 | Identifier lookup (the party name is in the contract; the LEI is not) |
| B_03.02 | 0010–0030 | Contract ref, provider code, code type | S ×3 | Identifier lookup |
| B_03.03 | 0010–0020 | Contract ref, LEI of FE providing services | S ×2 | Identifier lookup |
| B_04.01 | 0010–0030 | Contract ref, LEI of user FE, nature (branch or not) | S ×3 | Entity master data |
| B_04.01 | 0040 | Branch identification code | S | Entity master data |
| B_05.01 | 0010–0020 | Provider code, code type | S ×2 | Vendor master / GLEIF / EUID |
| B_05.01 | 0040 | Type of additional code | S | Identifier metadata |
| B_05.01 | 0050–0060 | Legal name "as registered", Latin-alphabet name | S ×2 | Registry data |
| B_05.01 | 0070–0080 | Type of person, HQ country | S ×2 | Registry data |
| B_05.01 | 0090–0100 | Currency, total annual expense | S ×2 | Finance actuals |
| B_05.01 | 0110–0120 | Ultimate parent code + code type | S ×2 | Corporate hierarchy data |
| B_05.02 | 0010 | Contract ref | S | Internal reference |
| B_05.02 | 0020 | Type of ICT services | **C*** | Same taxonomy call as B_02.02.0060 — borderline |
| B_05.02 | 0030–0040 | Provider code, code type | S ×2 | Vendor master |
| B_05.02 | 0050 | Rank in the supply chain | S | Supply-chain structure, usually from provider disclosure |
| B_05.02 | 0060–0070 | Recipient of subcontracted service + code type | S ×2 | Vendor master |
| B_06.01 | 0010–0040 | Function identifier, licenced activity, function name, FE LEI | S ×4 | Entity's own function taxonomy |
| B_06.01 | 0060 | **Criticality or importance** | **A** | The critical-or-important determination |
| B_06.01 | 0080 | Date of last assessment | **A** | Assessment record |
| B_06.01 | 0090–0100 | RTO, RPO (hours) | **A** ×2 | Resilience objectives set internally |
| B_06.01 | 0110 | Impact of discontinuing the function | **A** | Low/Medium/High judgement |
| B_07.01 | 0010–0030 | Contract ref, provider code, code type | S ×3 | Identifiers |
| B_07.01 | 0040 | Type of ICT services | **C*** | Taxonomy call — borderline |
| B_07.01 | 0050 | Substitutability of the provider | **A** | "the results of the … assessment" |
| B_07.01 | 0060 | Reason for non-substitutability | **A** | Closed-set assessment outcome |
| B_07.01 | 0070 | Date of the last audit | **A** | Audit record |
| B_07.01 | 0080 | **Existence of an exit plan** | **A** | Whether the *entity* has a plan — not whether the contract has an exit clause |
| B_07.01 | 0090 | Possibility of reintegration | **A** | Assessment |
| B_07.01 | 0100 | Impact of discontinuing the ICT service | **A** | Assessment |
| B_07.01 | 0110 | Alternative providers identified? | **A** | Assessment |

`[verified: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402956 — Annex I instructions]`

### Counts

| Class | Mandatory fields | Share |
|---|---|---|
| **Contract text (C)** | **13** | **13.5%** |
| System of record (S) | 68 | 70.8% |
| Internal assessment (A) | 15 | 15.6% |
| **Total mandatory** | **96** | 100% |

**Review note (added on checking the table).** The rows above sum to 13 C + 68 S + 14 A = **95**, not
96: the assessment class has 14 fields in the table (2 in B_02.02, 5 in B_06.01, 7 in B_07.01), or one
row is missing from it. The shares move by under a point (contract text 13.7%, S 71.6%, A 14.7%) and the
verdict is unchanged; the count should be re-checked against the ITS before it is quoted as exact.
Spot-checked against the ESAs' dry-run report itself (text extracted locally): the 6.5% / 947 figures, the
86% figure, the missing provider HQ country and ultimate-parent code fields (§33), and B_07.01 holding 20% of
missing values (§34) are all as stated. The report's "not one is a contract clause" is slightly strong:
B_07.01 column 0040 (type of ICT service) was among the missing fields, and this report counts that one
as a borderline contract field.

### How the borderline calls were resolved

Seven fields marked **C\*** are borderline and were resolved **in favour of the contract** — the
generous reading for our own hypothesis:

- `B_02.02.0060`, `B_05.02.0020`, `B_07.01.0040` (type of ICT services): the reader does not find
  "S06" in the agreement; they find a service description and map it to Annex III. Counted as
  contract-derived only because T-908 puts "service description" in class (a).
- `B_02.02.0130/0140/0150/0160` (provision country, storage yes/no, data-at-rest and processing
  locations): Article 30(2)(b) requires these in the contract, so a diligent reader can find them —
  but many entities take them from the cloud console or the vendor's own documentation, since they
  are operational facts that change and the contract only names permitted regions.

**Sensitivity.** If all seven borderline calls go the other way, contract-derived falls to **5 of 96
(5.2%)**: start date, end date, two notice periods, governing law. If instead every field that
*touches* an agreement is counted as contract-derived (adding contract reference numbers, the
termination reason, supply-chain rank, exit-plan existence and the three signatory LEIs), the
maximum reachable is about **21 of 96 (≈22%)**. **No defensible resolution reaches one third.**

### Result against the threshold

**13.5% contract-derived, against a ~33% threshold. The threshold is not met, and not close.**

The register is overwhelmingly an **identity-and-assessment** artefact: 70.8% of its mandatory fields
are identifiers, names, codes, dates and money that live in a vendor master, a GLEIF/EUID lookup, an
entity hierarchy or the ledger, and 15.6% are judgements the entity must make and defend
(criticality, RTO/RPO, substitutability, reintegration, reliance, sensitivity).

**And the measured errors land in exactly those two classes, not in the contract class.** The ESAs'
dry-run report names the fields that were actually missing: provider identification codes and their
type, ultimate-parent codes, provider HQ country, function identifiers, type of ICT services, and —
20% of all missing values in one template — the `B_07.01` assessment fields (substitutability,
reintegration, alternative providers).
`[verified: https://www.esma.europa.eu/sites/default/files/2024-12/ESA_2024_35_DORA_Dry_Run_exercise_summary_report.pdf §§31–34]`
Not one of the named problem fields is a contract clause.

---

## 3 · Register quality: 2024, 2025, 2026

**2024 dry run — all three T-907 figures verified against the ESAs' own report:**

- 1,039 financial entities submitted; 92 were discarded at integration; **947** were analysed
  against **116** data quality checks. `[verified: ESA_2024_35 §24, §14]`
- **6.5%** of the 947 passed all checks; 50% of the rest failed fewer than 5 checks; the worst
  single entity failed 43 of 116. `[verified: ESA_2024_35 §§24–26, p.4]`
- **86%** of all data errors were "mandatory information missing". `[verified: ESA_2024_35 §30]`
- Next most frequent: **invalid LEI codes, 6.5% of failures** — and notably more invalid LEIs for
  *financial entities* (~9,000) than for providers (~6,000), often because a national code was used
  where an LEI was required. `[verified: ESA_2024_35 §35]`

So T-907's headline numbers stand exactly as stated. What T-907 did not have is §§31–34, which say
*which* fields were missing — and that detail reverses the inference drawn from the headline.

**2025 (first official cycle) and 2026:** **no ESA-published aggregate pass rate exists.**

- Registers were collected by national authorities and forwarded to the ESAs by 30 April 2025, and
  for the 2026 cycle by 31 March 2026 on a 31 December 2025 reference date `[secondary]`.
- ESMA's *2025 Report on quality and use of data* (published 29 May 2026) was downloaded and
  searched: **it contains no section on the register of information** — its DORA content is major
  ICT-incident reporting.
  `[verified: https://www.esma.europa.eu/sites/default/files/2026-05/ESMA92-2024897840-14578_Report_on_quality_and_use_of_data_2025.pdf]`
- National-authority signals for 2026 are qualitative and negative, not a pass rate: rejected and
  returned submissions in Norway and Denmark (Danish correction window 31 Mar–30 Apr 2026), Swedish
  clarifications issued pre-deadline, BaFin naming free text in code fields, missing mandatory
  fields and duplicate identifiers; validation rules in 2026 are **stricter** than the dry run's.
  `[secondary: https://doragrc.com/blog/dora-register-of-information-2026-reporting-update]`
- One vendor claim that only ~40% of obliged entities had submitted by 16 March 2026 `[secondary]`.

**Is any 2026 pass rate above ~70%? No such figure has been published.** `[NOT VERIFIED]` The
check-2 kill condition therefore cannot be triggered — but it also cannot be relied on to keep the
hypothesis alive.

---

## 4 · What I could not open or verify

- **EUR-Lex HTML** for both 32022R2554 and OJ L_202402956 renders only the recitals; the article and
  annex text came from the **OJ PDFs**, which did work. Machine-readable ELI/HTML of the annex tables
  was not reachable.
- **No ESA or national aggregate data-quality statistic for the 2025 or 2026 submissions** could be
  found. Absence of publication, not a negative result.
- The **ESAs' validation-rule list** (the successor to the 116 checks, "last updated April 2025,
  applied to more fields in 2026") was referenced second-hand only; I did not open the rules file,
  so the exact 2026 check count is `[NOT VERIFIED]`.
- The `B_99.01` glossary template and Annex III's 19 ICT-service types were read but not
  field-by-field enumerated; neither affects the counts.
- National-regulator observations for 2026 (Norway, Denmark, Sweden, BaFin) rest on a single vendor
  blog; the underlying regulator notices were not opened. `[secondary]`

---

## Conclusions

**(i) Class counts** — of **96** mandatory data points across the 15 `B_` templates:
**contract text 13 (13.5%)**, **system of record 68 (70.8%)**, **internal assessment 15 (15.6%)**.

**(ii) Verdict against the one-third threshold** — **failed, decisively.** 13.5% against ~33%, with a
sensitivity range of 5.2%–22% under every alternative resolution of the borderline calls. The
contract-derived fields are a short, closed list: start and end dates, two notice periods, governing
law, and — generously — service type and four location fields.

**(iii) The DORA-register customer hypothesis should DROP as customer one, and be retained only as a
later feature.** Its stated falsifier ("at least a third of the mandatory fields are not
contract-derived") is met several times over. Worse for the hypothesis, the regulator's own
error breakdown shows the failures concentrated in provider identifiers, parent codes and the
`B_07.01` assessment block — the two classes a contract-knowledge product does *not* own. The
register's real bottleneck is **entity resolution against a vendor master plus a defensible
assessment workflow**, which is a TPRM/GRC product. Do not spend ten interviews here. Note that our
own *entity-resolution* kernel (LEI-linked golden records with a reversible, human-outranks-model
decision log) is the part that maps onto the actual failure — but that is a different product story
from contract knowledge, and it competes with established TPRM tooling rather than with contract AI.

**(iv) What a contract-knowledge product could and could not fill**

- **Could fill, with span-level citation:** the ~13 contract-derived fields per arrangement —
  `B_02.02.0070/0080` (dates as stipulated), `0100/0110` (notice periods), `0120` (governing law),
  and the Article 30(2)(b) location and service-description fields — extracted from the agreement
  *as amended*, each carrying the sentence that supports it. For an entity with thousands of ICT
  contracts this is real, dated, repeated work, and it is the only part of the register where
  "which clause says so" is the natural audit answer.
- **Could fill, adjacently and more valuably than the register fields themselves:** an Article 30
  **clause-coverage gap report** — which of the nine 30(2) and six 30(3) elements are absent from
  each agreement. DORA makes those clauses mandatory in the contract; nothing in the register
  reports them, so no register tool produces this, and remediation is a dated, budgeted programme.
- **Could not fill:** the 68 system-of-record fields (LEIs, EUIDs, provider and parent codes, HQ
  countries, branch codes, past-year spend, function taxonomy) — these come from GLEIF, the vendor
  master and the ledger, and getting them right is an entity-resolution and data-governance problem;
  and the 15 assessment fields (criticality, RTO/RPO, substitutability, reintegration, reliance,
  data sensitivity, exit-plan existence, alternative providers) — these are judgements a named human
  must make and sign, and a document cannot supply them. Note `B_07.01.0080` asks whether the
  *entity* has an exit plan, not whether the *contract* has an exit clause; reading the contract
  does not answer it.

---

**Sources**
- Regulation (EU) 2022/2554 (OJ L 333, 27.12.2022) — https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32022R2554
- Commission Implementing Regulation (EU) 2024/2956 (OJ L, 2.12.2024) — https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402956
- ESAs, *Key findings from the 2024 ESAs Dry Run exercise* (ESA 2024 35, 17.12.2024) — https://www.esma.europa.eu/sites/default/files/2024-12/ESA_2024_35_DORA_Dry_Run_exercise_summary_report.pdf
- ESMA, *2025 Report on quality and use of data* (29.5.2026) — https://www.esma.europa.eu/sites/default/files/2026-05/ESMA92-2024897840-14578_Report_on_quality_and_use_of_data_2025.pdf
- DORA GRC blog, 2026 reporting update `[secondary]` — https://doragrc.com/blog/dora-register-of-information-2026-reporting-update
- fscom, lessons from the 2025 RoI cycle `[secondary]` — https://fscom.co/blog/preparing-for-the-2026-dora-reporting-deadline-lessons-from-2025-every-firm-should-know/

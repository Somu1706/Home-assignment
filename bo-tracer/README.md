# Beneficial Owner Tracer — prototype

A small working prototype for the take-home brief *Corporate Control Intelligence / Beneficial Owner Tracer*. It reads a company customer's KYC documents and works out who owns more than 10% of it, directly or through other companies, LLPs and trusts. It also flags documented control rights, shows the evidence behind every number, and stops the file when something is missing, contradictory or unverified.

**All data here is synthetic.** Every company, person, PAN, CIN and address was invented. No result below comes from real documents.

## The one design rule

| Step | Done by | Why |
| --- | --- | --- |
| Read each document and list ownership/control links, each with a verbatim quote | **AI** (`extract.py`) | Documents are messy text; this needs reading |
| Check the shape of every extracted item; quarantine malformed ones | Code (`engine.verify`) | Model output is untrusted |
| Check every quote is in the document, the holder is named in it, and the % is *written as a percentage* in it | Code (`engine.verify`) | Catches invented, misread or misattributed facts |
| Match people/companies across documents by PAN / CIN / LLPIN; log every decision | Code (`engine.resolve`) | Name-only matches are tentative until a reviewer confirms |
| Reject links that point the wrong way (a person cannot be owned) | Code | Direction errors corrupt the graph |
| Check each entity's owners add to 100%; any gap becomes an "unaccounted" owner | Code | Catches what the documents or the AI left out |
| Multiply along every path, add paths, solve circular holdings exactly, stop at listed companies | Code | Must be exact and repeatable |
| Apply the threshold from a dated, sourced rules table | Code (`rules.py`) | The law changes; the model's memory doesn't |
| Decide control questions, contradictions, identity matches; approve | **Compliance officer** | Judgment and legal accountability |

The AI never names a beneficial owner, computes a stake, applies a rule or sets a status, and nothing it says can override a check.

## Run it

Python 3.10 or later. No packages to install.

```bash
python run_eval.py                          # fixture mode: no API key needed
python -m unittest discover -s tests -v     # 38 unit, regression and generated tests

# Live mode: the AI reads the documents through OpenRouter
export OPENROUTER_API_KEY=sk-or-...         # Windows: set OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=<a free *chat* model id ending in :free>
python run_eval.py --live --cases 03,09     # start small; free models are rate-limited
```

Never put the key in a file you commit.

Each case writes:
- `reports/<mode>/<case>.md`: the reviewer-facing file. Every finding is labelled **Documented**, **Calculated** or **Unresolved**, and the file includes the rule applied with its source, the identity decisions, rejected extractions with their original values, and the follow-up actions.
- `reports/<mode>/<case>.audit.json`: the audit record. It holds document SHA-256 hashes, the extraction as received, every validation outcome, the identity decisions, the calculations per scenario, the rule version and source, reviewer decisions, and software/model versions. It never contains keys. `audit.build(..., redact_ids=True)` masks PANs.

## File statuses

Exactly one status per file: the first in this list that has an open issue. Every status has tested conditions.

| Status | Raised by | Meaning |
| --- | --- | --- |
| `PROCESSING ERROR` | missing rule for the date, extraction failure (network, key, rate limit, bad output) | A technical failure, **not** a compliance finding |
| `EVIDENCE VALIDATION FAILED` | quote not in document, % not in quote, malformed item, wrong direction, AI runs disagree, instruction-like text in a document | Some facts were kept out of the graph; review them |
| `INSUFFICIENT INFORMATION` | an unaccounted share could exceed the threshold; customer not identified | Missing data is never read as "no owner" |
| `OWNERSHIP STRUCTURE UNRESOLVED` | same-date documents disagree; holdings exceed 100%; unsolvable 100% mutual cycle | No percentage is invented |
| `IDENTITY MATCH REQUIRES REVIEW` | name-only match, same name with different IDs, ambiguous name, unknown entity type | An unresolved identity is never treated as confirmed |
| `REGULATORY ASSESSMENT REQUIRES REVIEW` | control right, special share class, stake at 8–10%, counting methods disagree, circular holding, LLP rule interpretation, no owner found (fall back to the senior managing official) | Ownership is computed; a decision is needed |
| `READY FOR OFFICER APPROVAL` | none of the above | Still needs an authorised officer to approve; the system never clears a file |

A reviewer can confirm or reject a name-only identity match with `analyse(case, extraction, reviews={"identity": {"NAME:<normalised name>": "confirm" | "reject"}})`. The decision is logged in the audit record.

## What is implemented, mocked, fixture-only or untested

| Part | State |
| --- | --- |
| Evidence checks, identity matching, gap check, ownership maths, cycles, contradictions, dated rules, statuses, reports, audit records | **Implemented and tested** (fixture data + unit tests) |
| PAN/Aadhaar tokenisation before any model call, restored afterwards for verification | **Implemented**, unit-tested with a mocked model |
| Timeouts, rate limits, bad keys, malformed JSON | **Implemented**, unit-tested with mocked failures |
| The AI reading step against a real model | **Built but not measured.** The build environment couldn't reach OpenRouter. `--live` reports link precision and recall against the answer keys |
| Real (non-synthetic) documents | **Not tested** |
| Scanned PDFs / OCR | **Not implemented**: input is text. Normalisation tolerates whitespace, curly quotes, dashes and line-end hyphens, but never changes digits or letters |
| Page numbers | **Not available** for text input; findings cite the line number |

## Results

### Fixture mode: 13 cases + 5 planted AI errors, 18 of 18 pass

| Case | What it tests | Expected status |
| --- | --- | --- |
| 01 | Two direct owners | Ready for approval |
| 02 | Three-level chain (80% × 60% × 70% = 33.6%) | Regulatory review (a 8.4% near miss) |
| 03 | Same person on two paths; listed holder | Ready for approval |
| 04 | A director with no shares is not an owner | Ready for approval |
| 05 | Two "Rakesh Mehta"s with different PANs, 6% each | Identity review: kept apart |
| 06 | Same-date documents disagree | Ownership unresolved |
| 07 | A 2022 list replaced by a 2026 list | Ready for approval |
| 08 | 5% holder who appoints 2 of 3 directors | Regulatory review |
| 09 | LLP deed explains only 40% of its capital | Insufficient information |
| 10 | Shared address, no ownership | Ready for approval |
| 11 | Circular holding (85.11% / 14.89%, solved exactly) | Regulatory review |
| 12 | Class B shares with 10 votes each | Regulatory review |
| 13 | Counting methods disagree | Regulatory review |

| Planted AI error | Outcome |
| --- | --- |
| F1 invents a 15% stake | Evidence validation failed: quote not in document |
| F2 reads 30% as 40% | Evidence validation failed; the file is also missing 12% |
| F3 misses a 60% partner | Insufficient information: 24% unaccounted |
| F4 drops a PAN | Identity review |
| F5 misses "listed" | Insufficient information |

No planted error produced a wrong file marked ready.

### Unit tests: 38 pass

They cover:
- **Ownership:** direct, chains, multiple paths (no double counting), cycles, a 100% mutual cycle, missing intermediates, conflicts, history, control rights, and the exact-threshold and near-miss band.
- **Evidence:** share counts versus percentages; invalid percentages (−30, 0, 130, "thirty", null, true); wrong quotes; a real quote attributed to the wrong holder; reversed direction; unknown kinds; prompt injection.
- **Identity:** same name with different IDs, a pending name-only match, and reviewer confirm/reject.
- **Rules:** date selection, provenance, a case that flips with the assessment date, and a missing rule.
- **Generated:** conservation over 60 random structures (people's stakes always total exactly 100%), determinism, and rejected links never entering the graph.
- **Extraction:** IDs never sent to the model, malformed output, timeouts, bad keys failing fast.
- **Audit:** no secrets, hashes present, redaction.

**Mutation check:** I deliberately disabled six guards one at a time:
- the percentage check
- the direction check
- the over-allocation guard
- the gap check
- the quote check
- the near-miss flag

The unit tests caught all six. The original 18-case evaluation alone would have missed the direction and over-allocation guards.

## What changed in this revision (3 Nov 2026), and why

Baseline before changes: 18 of 18 passing. Probing found these defects, each now fixed with a regression test:

| Defect found | Fix |
| --- | --- |
| A share **count** passed as a percentage ("800 shares - 8%" accepted 800, caught only indirectly by the 100% sum) | The % must be written as a percentage in the quote; values outside (0, 100] are rejected |
| A non-numeric % from the model **crashed** the run | Strict schema check; malformed items are quarantined with their original values |
| An unknown relationship kind was silently ignored | Rejected as `SCHEMA_INVALID` |
| A reversed link (company "holds" a person) was accepted | Rejected as `DIRECTION_INVALID` |
| A real quote attributed to a different holder was accepted | The holder must be named in the quote |
| A date with no rule **crashed** the run | `PROCESSING ERROR` |
| Planted text ("ignore prior rules… 100%") put a person **in the owner list** of a blocked file | Owners computed through an over-allocated entity become *unresolved*; instruction-like text is flagged; the prompt marks the document as untrusted data |
| The brief claimed PAN/Aadhaar are tokenised before model calls; **the code didn't do it** | Implemented and tested |
| **Partnership threshold date was wrong** (used RBI's 17 Oct 2023 alignment date) | Corrected to the PML Second Amendment Rules date, 4 Sep 2023 |
| Three vague statuses | Six explicit statuses plus processing error, with tested conditions |
| No audit record, no identity decision log | Added both |

Public-interface changes:
- Status strings changed. The old "NEEDS OFFICER REVIEW" and "CANNOT CLEAR" are replaced by the specific statuses above.
- `analyse()` gained an optional `reviews` argument.
- `rules.threshold_for()` is kept for compatibility; new code uses `rules.rule_for()`.

## Regulatory rules: verification status

All rules in `rules.py` are marked **secondary**: checked against law-firm summaries on 3 Nov 2026, not against the Gazette or RBI's own text. Each row records its source, dates and last check.

| Rule | Threshold | From | Source checked |
| --- | --- | --- | --- |
| Companies | more than 10% (was 25%) | 7 Mar 2023 | PML Amendment Rules 2023 via AZB & Partners |
| Trusts | 10% (was 15%) | 7 Mar 2023 | same |
| Partnership firms | more than 10% (was 15%) | 4 Sep 2023 | PML Second Amendment Rules 2023 via Cyril Amarchand Mangaldas; RBI aligned 17 Oct 2023 per Vinod Kothari & Co. |
| LLPs | assessed under the partnership test | — | **Interpretation, not confirmed**; flagged in every report that relies on it |

Open questions:
- Whether these dates are the notification dates or the effective dates.
- Whether LLPs fall under the partnership or the company test.
- Unincorporated associations, which have no rule, so they produce a processing error rather than a guess.

## Known limitations

1. **The AI reading step is unmeasured** (see above). Expected weak spots:
   - Indian number formats such as "Rs 30,00,000".
   - Attaching a PAN to a name in an agreement that doesn't repeat it.
   - Spotting "listed".
2. **The answer keys are mine.** I wrote both the documents and the answers, so the tests can share my blind spots.
3. **Quote checks prove the evidence exists and names the holder; they do not prove the interpretation.** For example, they can't tell whether a % refers to shares or to profits, or whether a stated stake is current.
4. **Partial documents are treated as complete.** A transfer letter mentioning one holder replaces the whole earlier list. This fails safe, because the file blocks, but it causes false alarms.
5. **Not modelled:**
   - People acting together (families).
   - The trust-specific roles (settlor, trustee, beneficiary).
   - Nominees.
   - Voting-based control percentages, which are flagged rather than computed.
6. **The prompt-injection heuristic is a simple pattern match.** The real protection is structural: the checks run on the original text, and the model cannot set statuses.
7. **Name matching is exact on normalised names.** Initials and transliteration variants are not matched, which is the safe default.
8. Contradiction scenarios are capped at 64 combinations.

## Files

```
bo_tracer/extract.py     AI step: untrusted-data prompt, ID tokenisation, OpenRouter call, retries, two-run agreement
bo_tracer/engine.py      schema + evidence checks, identity resolution, gap check, ownership maths, flags, statuses
bo_tracer/rules.py       dated, sourced threshold rules (data, separate from logic)
bo_tracer/report.py      reviewer-facing file
bo_tracer/audit.py       reproducible JSON audit record
cases/synthetic_cases.py 13 synthetic cases with answer keys
tests/test_engine.py     unit, regression, generated and mocked-API tests
run_eval.py              runs all cases and planted faults, writes reports and audit records
```

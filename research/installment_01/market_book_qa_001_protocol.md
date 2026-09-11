# MARKET-BOOK-QA-001 — Bookmaker Historical Coverage Gate

Status: **PREREGISTERED / PRE-RESULT**

## Purpose

Decide whether the exact MARKET-BOOK-001 artifact is sufficiently complete for the already-frozen MARKET-EDGE confirmatory information-overlap tests before any signal-vs-market outcome is inspected.

The QA gate is about source integrity, identity coverage, chronology, and usable two-sided closing-market coverage. It cannot promote Profile Gap or Genome and cannot inspect their predictive performance.

## Inputs

- frozen bookmaker source manifest;
- MARKET-BOOK-001 canonical records;
- canonical pre-match table;
- canonical outcome ledger only for completed-match eligibility (`walkover`/`retirement` removal).

The pre-match table must remain outcome-free.

## Eligible denominator

For each tour/year, denominator rows are canonical matches inside the declared source interval that are completed and are neither walkovers nor retirements.

The outcome ledger is used only to establish that eligibility. `a_won`, score, model probability, Profile Gap, Genome, or any loss/edge calculation is outside this QA experiment.

## Usable numerator

A denominator match counts as covered only when MARKET-BOOK-001 has exactly one selected `BOOKMAKER_CLOSE_V1` quote that:

- is joined `MATCHED` to that canonical match;
- has two finite decimal odds greater than 1.0;
- has finite no-vig probabilities strictly inside `(0,1)` that sum to 1 within numerical tolerance;
- follows the frozen Valuebetennis -> Tennis-Data/Pinnacle hierarchy;
- has no within-source conflict;
- is dated no later than 2025-12-31.

## Frozen per-tour confirmatory gates

Each of ATP and WTA independently must satisfy all of:

1. overall usable closing-market coverage >= 60%;
2. usable coverage >= 50% in every evaluation year 2021, 2022, 2023, 2024, 2025;
3. at least 100 usable closing quotes in every evaluation year 2021-2025;
4. at least 1,000 usable joined prior rows dated before 2021-01-01;
5. all five evaluation years 2021-2025 represented.

Global status is `ELIGIBLE_CONFIRMATORY` only when both tours pass every gate.

No threshold may be relaxed after seeing MARKET-EDGE results.

## Required diagnostics

Report without using winners/model results:

- denominator and usable counts overall and by tour/year;
- coverage percentages overall and by tour/year;
- selected-source counts overall and by tour/year;
- matched/unmatched/ambiguous counts by source;
- missing-invalid-quote and within-source-conflict counts;
- pre-2021 usable depth;
- overlap count where both sources independently provide valid joined quotes;
- on overlap only, absolute difference in no-vig probability for canonical A, summarized by count, mean, median, p90, p95, and maximum;
- source-file and artifact hashes.

Overlap disagreement is diagnostic only. It cannot be used to choose the source per match because the source hierarchy was frozen before outcomes.

## Structural fail-closed rules

QA must reject, rather than grade, artifacts when:

- source manifest or record hashes do not verify;
- the artifact contains a selected 2026-or-later quote;
- one canonical match has more than one selected primary quote;
- a selected record violates the frozen source priority;
- market probability is malformed;
- canonical pre-match input contains outcome fields;
- a record's join hash/provenance is inconsistent.

## Status classes

- `ELIGIBLE_CONFIRMATORY`: both ATP and WTA pass every frozen gate.
- `INSUFFICIENT_COVERAGE`: structurally valid artifact, but at least one frozen coverage/depth gate fails.

Structural integrity violations raise an error and do not produce a permissive status.

## What QA may change

Before MARKET-EDGE results are opened, a failed QA may justify acquiring additional historical source data that obey the same frozen source semantics and hierarchy.

It may not justify:

- substituting opening odds for closing odds;
- selecting a different bookmaker because it improves later model performance;
- lowering coverage/count/prior-history gates;
- excluding difficult years or probability regions after results;
- changing the four-claim multiplicity family.

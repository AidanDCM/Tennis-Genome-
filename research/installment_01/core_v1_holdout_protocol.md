# Core v1 — Sealed 2026 Holdout Protocol

Status: **pre-registered before any 2026 family/core holdout result is inspected**

Purpose: prevent the promoted foundational model from being declared successful merely because its families were selected on the same 2000–2025 historical population used to measure them.

---

## Sealed holdout

All accepted family discovery and grading uses completed seasons 2000–2025 only.

The pinned archival snapshot also contains partial 2026 ATP/WTA match files, but those files were deliberately excluded from:
- EXP-001 discovery;
- EXP-002 discovery;
- EXP-003 discovery;
- FOUNDATIONAL-FAMILY-LAB-001;
- family grading.

Those available 2026 matches are therefore reserved as a **partial forward holdout**.

The holdout is not a complete 2026 season and must never be described as one. Its value is temporal non-use, not season completeness.

---

## Feature selection rule

The final Core v1 A-family list is determined before reading the 2026 holdout.

A provisional A family from `foundational_family_findings.md` remains A only if the reporting-only recent-block diagnostic shows no obvious collapse in the last five evaluated 2000–2025 seasons.

No B, C, or D family may be promoted because of 2026 results.

If a provisional A fails the recent-block gate, it is excluded from the A-only Core v1 before any 2026 score is read.

---

## Models to compare

For each tour, train using 2000–2025 only and predict the available 2026 matches.

### Historical core benchmark
- chronologically constructed overall Elo;
- opponent-adjusted serve/return only where it already belongs to the validated historical core for the tour/reporting comparison.

### Core v1 A-only candidate
- overall Elo;
- every family receiving final A grade under the pre-registered family rules;
- no B/C/D family.

A secondary diagnostic may report an A-plus-B model, but it cannot replace the A-only primary comparison and cannot promote a B family.

---

## Training discipline

1. Build historical feature state through the end of 2025 without using 2026 outcomes.
2. Fit missing-value handling, scaling, and model coefficients on 2000–2025 only.
3. Generate 2026 probabilities from frozen pre-match state.
4. Do not refit within the holdout after seeing any 2026 outcome for the primary result.
5. Score only after all eligible 2026 predictions are frozen.

Because the source lacks trustworthy exact match timestamps, the same conservative source-date freezing rules remain in force.

---

## Primary metrics

1. Brier score;
2. binary log loss.

Secondary:
- accuracy;
- 10-bin ECE;
- sample size;
- ATP/WTA separately.

The Core v1 candidate is considered a successful first forward confirmation only if it improves both Brier and log loss versus the historical core on the available 2026 holdout for that tour.

Accuracy may be reported but cannot override worse probability quality.

---

## Interpretation

A positive partial-2026 result is meaningful forward evidence, not proof of profitability or permanence.

A negative result blocks an unconditional Core v1 promotion and triggers diagnosis; it must not be repaired by changing features after inspecting the same holdout and then re-labeling the repaired model as independently validated.

Any post-holdout change creates a new candidate that requires a new future holdout.

---

## Market separation

No bookmaker odds enter this holdout. This remains an independent tennis probability-engine test.

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

For each tour, fit model parameters using 2000–2025 only and predict the available 2026 matches in chronological source-date order.

### Historical core benchmark
- chronologically constructed overall Elo;
- opponent-adjusted serve/return only where it already belongs to the validated historical core for the tour/reporting comparison.

### Core v1 A-only candidate
- overall Elo;
- every family receiving final A grade under the pre-registered family rules;
- no B/C/D family.

A secondary diagnostic may report an A-plus-B model, but it cannot replace the A-only primary comparison and cannot promote a B family.

---

## Training and forward-state discipline

1. Fit missing-value handling, scaling, and model coefficients using 2000–2025 only.
2. Freeze those fitted model parameters before the first 2026 prediction.
3. Generate 2026 predictions sequentially in source-date order.
4. Dynamic player state such as Elo, serve/return strength, form, H2H, workload, and prior-match state **may update from genuinely earlier 2026 matches**, because those outcomes would have been available in real forward deployment.
5. A 2026 match may never affect its own features or any match on the same unresolved source date; existing conservative date-batching remains mandatory.
6. Model coefficients, scalers, imputers, family membership, and hyperparameters must **not** be refit or changed using 2026 outcomes.
7. Freeze every eligible 2026 probability before using that match outcome for scoring.
8. Score the holdout only after the complete available 2026 prediction sequence has been generated.

This distinction is deliberate: **player state is allowed to evolve as new public match results arrive; the predictive mapping learned from 2000–2025 remains frozen.** That mirrors deployment while preserving a genuine forward model test.

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

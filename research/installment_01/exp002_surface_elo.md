# EXP-002 — Overall Elo vs Surface Elo

Status: **implementation-ready; real-data run pending source approval/audit**

## Research question

Does a pure surface-specific Elo model improve future pre-match probability quality over the same overall Elo model when both are trained chronologically on the same known-surface professional singles matches?

This experiment tests whether separating player strength by playing surface adds useful predictive information. It is not a profitability test.

---

## Null / alternative

**H0:** Surface-specific Elo does not improve out-of-sample probability quality relative to overall Elo.

**H1:** Surface-specific Elo improves future probability quality, or provides a stable complementary signal that justifies promotion into later hybrid models.

No result is promoted because of accuracy alone. Brier score, log loss, calibration, stability, effect size, and sample size matter.

---

## Population

Initial analysis:
- ATP and WTA run separately.
- Completed professional singles matches from the audited canonical source.
- Matches with `surface == Unknown` excluded from both models and from their training history.
- Walkovers excluded.
- Primary view excludes retirements.
- Retirement-inclusive sensitivity view may be run separately and labeled.
- Overall Elo and Surface Elo are scored on the exact same match IDs.

The known-surface filter is applied before either model is evaluated so overall Elo cannot gain extra training information unavailable to Surface Elo.

---

## Data boundary

EXP-002 consumes only canonical:
- provenance manifest,
- `*_pre_match.parquet`,
- `*_outcomes.parquet`.

The CLI verifies manifest hashes and research-use permission before loading the dataset.

Provider-specific raw CSV/API responses are not legal experiment inputs.

---

## Overall Elo

One rating per player across all known surfaces.

Starter configuration:
- initial rating: `1500`,
- K factor: `32`,
- logistic scale: `400`.

These are baseline parameters, not claimed optima. Any tuning must be a separately registered chronological experiment and must not use the final evaluation period.

---

## Surface Elo

Separate rating per player per surface:
- Hard,
- Clay,
- Grass,
- Carpet.

A player's result on one surface updates only that surface rating.

Version 1 intentionally does **not** include:
- overall/surface blending,
- cross-surface priors,
- surface similarity transfer,
- rating decay,
- surface-specific K factors,
- inactivity adjustment,
- recency weighting,
- tournament-level weighting.

Those belong to follow-up hypotheses only if pure Surface Elo demonstrates useful structure or clearly exposes a cold-start weakness worth addressing.

---

## Same-day timing rule

If exact match start times are not trustworthy, both overall Elo and Surface Elo freeze ratings before the calendar date and apply all same-day deltas after predictions for that date.

CSV row order is never used as hidden chronology.

---

## Primary metrics

1. Brier score — lower is better.
2. Binary log loss — lower is better.
3. 10-bin ECE diagnostic.
4. Accuracy — descriptive/secondary only.

The report stores the exact initial rating, K factor, and scale used.

---

## Required slices

Report:
- aggregate common-population performance,
- year-by-year performance,
- performance separately for Hard, Clay, Grass, and Carpet where present,
- ATP/WTA as separate runs.

Surface-specific conclusions must respect sample size. A strong Grass result on a tiny population cannot be generalized to all surfaces.

---

## Required adversarial checks

Before promotion:

1. Confirm both models train on the identical known-surface match stream.
2. Confirm a Hard result cannot update a player's Clay/Grass/Carpet Surface Elo.
3. Confirm unknown-surface matches update neither model in EXP-002.
4. Confirm same-day order cannot alter predictions under date-only timing.
5. Confirm target-match outcomes never enter their own pre-match probabilities.
6. Confirm score comparison uses identical match IDs.
7. Inspect year-by-year reversals.
8. Inspect each surface separately.
9. Run retirement sensitivity separately.
10. Preserve the exact Elo configuration in the result artifact.
11. If parameters are tuned later, use nested chronological tuning and retain an untouched final period.

---

## Interpretation rules

Possible outcomes:

### Surface Elo clearly wins
Promote Surface Elo as an A/Core candidate and test a hybrid overall + surface model next.

### Surface Elo wins only on some surfaces
Treat it as B/Conditional. Investigate whether a surface-specific or blended model is justified rather than forcing one global rule.

### Surface Elo is worse early but better after experience
Register a cold-start / shrinkage hypothesis. Do not retroactively add priors and call the original experiment successful.

### Surface Elo loses overall
Keep the result. The likely next question is whether surface information belongs as a smaller adjustment to overall strength rather than as independent rating universes.

---

## Current implementation entry point

```bash
python -m tennis_genome.experiments.exp002 \
  --manifest data/processed/atp_manifest.json \
  --pre-match data/processed/atp_pre_match.parquet \
  --outcomes data/processed/atp_outcomes.parquet
```

Optional explicit parameters:

```bash
  --initial-rating 1500 \
  --k-factor 32 \
  --scale 400
```

Run WTA separately.

---

## Not yet claimed

EXP-002 has not yet been run on an approved real historical dataset in this repository. No Surface Elo improvement, accuracy, calibration, or betting edge is currently a Tennis Genome result.

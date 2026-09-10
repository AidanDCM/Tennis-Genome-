# FUSION-CAL-001 — Tour-specific probability fusion protocol

Status: preregistered before historical result inspection.

## Purpose

Test whether the validated historical-alignment probability contains enough incremental information beyond the calibrated strict-Core probability to justify a separate fusion layer, and determine whether the resulting candidate requires a new chronological calibration layer.

This is a development experiment, not independent forward confirmation. The partial-2026 sample is already spent and remains excluded.

## Evidence inherited from earlier milestones

- strict Core remains the main market-blind parametric probability engine;
- GENOME-ADV-001 established different historical-alignment candidates by tour:
  - ATP: full Genome historical residual neighborhood;
  - WTA: strict-Core-geometry historical residual neighborhood;
- the historical-alignment predictor itself is not an independent model family: it is a chronological meta-model built from Core probability plus a historical residual signal;
- CAL-SEL-001 retained ATP Identity calibration and selected WTA Beta as a development calibration candidate for the older strict-Core architecture;
- UNCERTAINTY-OOD-001 did not promote a universal uncertainty composite.

Therefore this experiment is correctly called **fusion**, not independent ensemble diversification.

## Data boundary

- source: the pinned research-only 2000–2025 Sackmann archival snapshot already used by the accepted experiments;
- selected-tour rows after 2025 fail closed;
- retirements and walkovers follow the accepted GENOME-ADV-001 eligibility rules;
- no sportsbook, market, odds, CLV, or future information is permitted;
- all training and calibration are chronological by calendar year.

## Base probability views

FUSION-CAL-001 first reproduces the accepted GENOME-ADV-001 prediction ledger using the existing implementation and fixed parameters:

- `p_core_control`: the one-input chronological Core calibration-control probability from GENOME-ADV-001;
- `p_alignment`:
  - ATP = `full_genome_probability_a`;
  - WTA = `core_neighborhood_probability_a`.

The exact same matched rows are used for every fusion comparison.

## Fusion candidates

For each outer test year, only rows from strictly earlier years may fit a fusion model.

### F0 — alignment identity

No additional fitting:

`p_F0 = p_alignment`

This is the incumbent historical-alignment probability.

### F1 — alignment-only recalibration control

Fit a standardized L2 logistic model on earlier rows using only:

`logit(p_alignment)`

This is the critical adversarial control. It measures what can be gained by giving the incumbent probability another chronological logistic calibration pass.

### F2 — fixed equal-logit blend diagnostic

No fitted weight:

`logit(p_F2) = 0.5 * logit(p_core_control) + 0.5 * logit(p_alignment)`

This is descriptive only and cannot receive the primary promotion decision.

### F3 — two-view chronological fusion

Fit a standardized L2 logistic model on earlier rows using:

- `logit(p_core_control)`
- `logit(p_alignment)`

Estimator:

`StandardScaler -> LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)`

No interaction terms, nonlinear learner, threshold tuning, or additional features are allowed in FUSION-CAL-001.

## Minimum history gates

- reproduce GENOME-ADV-001 with `min_core_train_matches=1000`, `min_neighbor_pool=1000`, `min_meta_train_rows=1000`, fixed `k=100`;
- fusion outer year requires at least 1,000 prior matched fusion rows and both outcome classes;
- test years without sufficient prior fusion rows are skipped identically for F1 and F3;
- F0 and F2 are scored only on the common F1/F3 population so every comparison has identical match IDs.

## Primary fusion question

Does F3 beat F1, not merely F0?

The project may claim **incremental fusion value** only if all frozen gates pass:

1. aggregate F3 Brier < F1 Brier;
2. aggregate F3 log loss < F1 log loss;
3. F3 jointly beats F1 on Brier and log loss in at least 60% of evaluated outer years;
4. 2021–2025 aggregate F3 Brier is not worse than F1;
5. 2021–2025 aggregate F3 log loss is not worse than F1.

If any gate fails, the second probability input is not promoted as a separate fusion layer. The incumbent tour-specific alignment probability remains the probability architecture candidate.

F2 is a sanity diagnostic only. It is never promoted over F1/F3 based on retrospective superiority.

## Diagnostic outputs

Report for every model:

- N;
- Brier;
- log loss;
- accuracy;
- ECE-10;
- aggregate and 2021–2025 metrics;
- year-by-year metrics on the exact common population.

For F3 also report the fitted standardized coefficients by outer year. Coefficients are diagnostic only; they are not post-hoc feature-selection rules.

Report the absolute probability disagreement `abs(p_core_control - p_alignment)` by quintile against Core/alignment error as a diagnostic of whether fusion gains concentrate where the two views differ. This does not create an uncertainty veto.

## Calibration follow-up inside this milestone

Calibration is evaluated only after F0/F1/F2/F3 predictions have been generated chronologically. It does not alter the fusion promotion gate above.

For each candidate independently, produce a **second nested chronological calibration ledger**. For each calibration test year, fit calibrators only on earlier out-of-sample predictions from that same candidate.

Registered calibrators:

- Identity;
- Platt;
- Beta;
- Isotonic.

Minimum calibration history: 1,000 earlier OOS candidate predictions and both classes.

### Calibration promotion gate

For a non-Identity calibrator to replace Identity for a given candidate, it must:

1. improve aggregate Brier;
2. improve aggregate log loss;
3. not worsen aggregate ECE-10 by more than 0.002 absolute;
4. improve both Brier and log loss on 2021–2025 aggregate;
5. jointly improve Brier and log loss in at least 60% of evaluated calibration years.

If multiple calibrators pass, choose the passing method with the lowest aggregate log loss; break an exact practical tie by lower Brier, then lower ECE-10, then simpler method order `Platt -> Beta -> Isotonic`.

The calibration result is a **development candidate only** because no untouched post-2025 forward sample remains.

## Architecture decision tree

- If F3 fusion gate passes: the tour's probability candidate becomes F3 plus its independently evaluated calibration decision.
- If F3 fusion gate fails: no two-view fusion layer is promoted; the tour remains on F0/alignment architecture plus the independently evaluated calibration decision for F0.
- F1 exists primarily as the adversarial calibration control and may not be relabeled as fusion.

## Claims explicitly forbidden

This experiment cannot establish:

- sportsbook edge;
- positive expected value;
- ROI/profitability;
- optimal staking;
- production readiness;
- independent forward validation;
- that Core and historical alignment are independent information sources.

## Required implementation tests

Before the historical run:

- outer fusion year never fits on target/future years;
- second-stage calibrator never fits on its target/future year;
- ATP selects full-Genome alignment; WTA selects strict-Core-geometry alignment;
- all model comparisons use identical match IDs;
- player-order probability symmetry is preserved;
- post-2025 selected-tour data fails closed;
- changing a target year's outcomes cannot change that same year's pre-outcome fusion probabilities.

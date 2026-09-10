# UNCERTAINTY-OOD-001 — preregistration

Status: **frozen before historical result inspection**

## Purpose

Test whether Tennis Genome can identify *when its strict Core probability is less trustworthy* using only information available before the target match.

This experiment is a new hypothesis. It does **not** repair or reinterpret the failed raw-density result from GENOME-NN-001. Raw `D100` remains rejected as an OOD/PASS coordinate.

The experiment has two related goals:

1. test individual pre-match uncertainty coordinates after controlling known confounding;
2. test whether those coordinates jointly rank future forecast risk better than Core probability confidence alone.

No uncertainty signal changes the match probability in this experiment. It only predicts the expected error/risk of the already-generated strict Core probability.

## Development data

- ATP and WTA are evaluated separately;
- pinned 2000–2025 research snapshot only;
- post-2025 selected-tour rows fail closed;
- the partial-2026 holdout remains spent and forbidden;
- normal-completion primary population excludes walkovers and retirements;
- all probability, profile, neighborhood, conditioning, and risk-model fits are chronological.

## Forecast being assessed

The target forecast is the **strict Core v1 OOS probability** generated for each outer year using only earlier-year training rows.

The uncertainty experiment does not switch to a different probability generator after seeing risk results.

## Historical-alignment representation

Use the representation frozen by GENOME-ADV-001:

- **ATP:** full Genome = strict Core geometry + permitted strict Profile absolute means;
- **WTA:** strict Core geometry only;
- primary neighborhood size: `k=100`;
- historical pool: strictly earlier OOS Core-ledger rows;
- distance: historical-pool-fitted median imputation + standardization + Euclidean distance;
- no distance weighting, k tuning, embedding, or metric learning.

Only neighbor **distance** is used here. Neighbor outcome residuals are not used by the uncertainty model.

## Candidate uncertainty coordinates

### U1 — Core probability confidence

`core_confidence = abs(p_core - 0.5)`

This is the baseline selective-prediction signal and is not considered a new discovery.

### U2 — difficulty-conditioned unfamiliarity

Raw mean k=100 distance is known to be confounded by match extremity and historical-pool growth.

For every uncertainty test year:

1. compute each target's raw mean k=100 distance against strictly earlier historical Genome rows;
2. use only **earlier uncertainty-evidence rows** to fit:

`log(D100) ~ core_confidence + core_confidence^2 + log(historical_pool_size)`

3. calculate the target residual from this expectation;
4. divide by the standard deviation of the prior training residuals.

The resulting z-score is `conditioned_unfamiliarity`.

Positive values mean the target is farther from history than expected for its Core confidence and the historical pool size available at that time.

No sign flip, outcome-based transformation, same-year distribution fitting, or post-result threshold is allowed.

### U3 — model disagreement

Use the pre-existing chronological probability views:

- Elo-only probability;
- strict Core probability;
- A+B diagnostic probability.

`disagreement = max(probabilities) - min(probabilities)`

This preserves the CAL-SEL-001 definition rather than inventing a new disagreement score after results.

### U4 — feature missingness

Use the missing fraction of the **tour-selected historical-alignment vector** before fold-fitted imputation.

- ATP: full-Genome vector missing fraction;
- WTA: strict-Core vector missing fraction.

### U5 — player-history depth

Primary universal depth coordinate:

`min_prior_matches = min(profile_A.prior_matches, profile_B.prior_matches)`

Risk model input is `log1p(min_prior_matches)`.

ATP additionally receives:

`min_prior_point_exposure = min(A serve points, A return points, B serve points, B return points)`

with input `log1p(min_prior_point_exposure)`, because ATP strict Core uses the validated serve/return state. This coordinate is not included in the WTA primary risk model because serve/return is not WTA strict Core.

## Chronology of distance conditioning

A row may receive `conditioned_unfamiliarity` only when at least **1,000 earlier distance-evidence rows** exist.

The conditioning regression is fit only on earlier rows. Target-year distances and target-year outcomes never refit the conditioning model.

If the prior conditioning-residual standard deviation is zero/non-finite, that year is not eligible.

## Chronological uncertainty-risk model

Target:

`brier_contribution = (p_core - y)^2`

For each outer risk-test year, fit only on earlier uncertainty-evidence rows that already possess legal conditioned-unfamiliarity values.

Estimator:

`StandardScaler -> Ridge(alpha=1.0)`

Primary inputs:

ATP:
- `core_confidence`
- `conditioned_unfamiliarity`
- `disagreement`
- `alignment_missing_fraction`
- `log1p(min_prior_matches)`
- `log1p(min_prior_point_exposure)`

WTA:
- `core_confidence`
- `conditioned_unfamiliarity`
- `disagreement`
- `alignment_missing_fraction`
- `log1p(min_prior_matches)`

Minimum earlier risk-training population: **1,000 rows**.

The Ridge output is a **risk ranking score only**. It does not recalibrate or alter `p_core`.

## Direct individual-signal diagnostics

For each eligible OOS uncertainty row, calculate actual Core:

- Brier contribution;
- log-loss contribution;
- absolute residual `abs(y - p_core)`;
- correctness at 0.5.

Report equal-count quintiles and linear slopes for:

- conditioned unfamiliarity;
- disagreement;
- alignment missing fraction;
- history depth.

Expected risk directions:

- conditioned unfamiliarity: **higher -> more error**;
- disagreement: **higher -> more error**;
- missingness: **higher -> more error**;
- history depth: **higher -> less error**.

Report aggregate and 2021–2025 diagnostics. Ties are broken by match ID, never outcome.

## H-012 conditioned-density gate

Difficulty-conditioned unfamiliarity is promoted from C/experimental only if all are true:

1. aggregate Brier-contribution slope vs conditioned unfamiliarity > 0;
2. aggregate log-loss-contribution slope > 0;
3. Q5-minus-Q1 Brier contribution > 0;
4. Q5-minus-Q1 log-loss contribution > 0;
5. 2021–2025 Brier and log-loss directions do not reverse.

Failure leaves H-012 rejected for operational uncertainty use. No raw-distance sign inversion is permitted.

## H-010 disagreement gate

Model disagreement is promoted as an uncertainty coordinate only if:

1. aggregate Brier and log-loss slopes are positive;
2. Q5-minus-Q1 Brier and log loss are positive;
3. 2021–2025 directions do not reverse.

This experiment may upgrade or reject the earlier B/conditional disagreement finding.

## H-017 missingness/depth gate

Missingness is supported only if its aggregate and recent Brier/log-loss directions are positive.

History depth is supported only if its aggregate and recent Brier/log-loss directions are negative (greater history -> lower error).

A coordinate can pass individually even if the combined risk model fails.

## Primary selective-risk comparison

Every risk-model prediction is OOS from earlier-year fitting.

For the same matched prediction population, compare two rankings:

### Confidence baseline

Sort by descending `core_confidence` (most confident retained first).

### Uncertainty model

Sort by ascending predicted Ridge Brier risk (lowest predicted risk retained first).

Evaluate Core probabilities at fixed coverage:

- 100%
- 75%
- 50%
- 25%
- 10%
- 5%

At each level report:

- Brier;
- log loss;
- accuracy;
- ECE-10;
- realized coverage;
- minimum/maximum retained risk as appropriate.

## Combined uncertainty promotion gate

The combined uncertainty model becomes an **Uncertainty v1 development candidate** only if all are true:

1. against confidence-only selection, it has lower Brier at at least **2 of 3** primary operational coverages: 75%, 50%, 25%;
2. it has lower log loss at at least **2 of 3** of those same coverages;
3. the mean Brier across 75/50/25 is lower than confidence-only;
4. the mean log loss across 75/50/25 is lower than confidence-only;
5. the 2021–2025 block satisfies the same mean-Brier and mean-log-loss direction;
6. its own retained-set Brier does not worsen as coverage moves 100% -> 75% -> 50% -> 25%;
7. no claim is based solely on 10% or 5% extreme-favorite subsets.

The 10% and 5% rows are diagnostics only for the promotion decision.

If the combined gate fails, individual uncertainty coordinates may still remain B/C candidates, but no composite PASS/risk score is promoted.

## Non-claims

UNCERTAINTY-OOD-001 cannot establish:

- a hard PASS threshold;
- independent future confirmation;
- market edge or sportsbook mispricing;
- EV, CLV, ROI, or profitability;
- optimal distance metric, k, Ridge penalty, or uncertainty feature set;
- that uncertainty causes forecast errors;
- that raw `D100` is useful.

Any hard abstention threshold requires a separate frozen policy experiment after this ranking study.

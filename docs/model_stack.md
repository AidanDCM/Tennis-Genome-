# Model Stack

## Philosophy

Complex models are challengers, not default winners. Every level must beat simpler baselines chronologically and probabilistically.

## M0 — Ranking baseline

Purpose: minimum competent benchmark.

Candidate inputs:
- ranking difference
- ranking-point difference/log ratio
- tour/event level

A simple logistic model is sufficient initially.

## M1 — Elo

Canonical Elo probability form:

`P(A) = 1 / (1 + 10^((R_B - R_A) / s))`

where scale `s` and update K/decay choices are validated chronologically rather than assumed.

Update only after each completed match.

Test:
- initialization
- K factor
- temporal decay
- margin/point variants only as separate experiments

## M2 — Surface Elo

Maintain surface-specific ratings with shrinkage toward overall Elo.

Questions:
- how much historical surface information is needed?
- should surface ratings decay differently?
- should indoor hard be separate?
- does tournament-level court pace add beyond nominal surface later?

## M3 — Serve/Return strength

Estimate opponent-adjusted serve and return ability, ideally using points rather than only match outcomes.

Conceptually estimate latent:
- serving ability
- returning ability
- surface effect
- opponent effect

Then derive expected service-point probabilities for the matchup.

Potential model families:
- regularized logistic models
- hierarchical generalized linear models
- Elo-like point ratings
- Bayesian partial pooling

## Match probability from point strength

Later, point-level serve probabilities can feed a game/set/match simulator.

This creates a mechanistic route:

`serve/return -> point probabilities -> games -> sets -> match`

Simulation assumptions must be validated; independent-point assumptions may be imperfect.

## M4 — Recent form

Recent form should focus on underlying performance residuals rather than raw wins.

Candidate inputs:
- opponent-adjusted point residuals
- serve residual trend
- return residual trend
- Elo change

Test windows and exponential decay chronologically.

## M5 — Player Profile

Candidate model families:
- regularized logistic regression
- gradient-boosted trees
- hierarchical/Bayesian models

GBM can capture nonlinear interactions, but must be compared with transparent models and calibrated.

## M6 — Workload / rest

Add validated fatigue/load variables and registered interactions.

Avoid hand-coded penalties unless learned from historical data and validated out-of-sample.

## M7 — Tennis Genome neighborhood

Candidate outputs from the historical alignment engine:
- neighbor residual mean
- weighted neighbor residual
- neighbor outcome calibration
- local density
- distance statistics
- module-specific residual summaries

These enter as experimental features or a standalone challenger model.

## M8 — Ensemble

Combine independently useful models.

Candidates:
- logistic stacking
- weighted probability average
- Bayesian model averaging

Stacking weights must be learned on validation windows, never final holdouts.

Ensemble value is highest when constituent models make different errors.

## Calibration layer

Treat calibration separately from predictive score fitting.

Evaluate:
- no calibration
- logistic/Platt
- isotonic
- beta calibration if justified

Calibrator must be trained only on prior data in each walk-forward fold.

## Uncertainty

Candidate uncertainty signals:
- bootstrap/model posterior interval
- disagreement across model family
- neighborhood density
- feature missingness/quality
- calibration bucket sample size
- prediction extremity / OOD distance

Do not pretend one scalar confidence score is correct until tested against future errors.

## Baseline acceptance hierarchy

A new model is preferred only if it shows meaningful improvement in primary metrics with acceptable stability.

Priority order:
1. calibration/log loss
2. Brier score
3. stability across periods/subgroups
4. selective-prediction behavior
5. accuracy

## Market model

Odds are excluded from M0–M8.

A separate market-aware meta-model may later test:
- independent probability
- market no-vig probability
- model-market disagreement
- line movement
- liquidity/source quality

This prevents the system from claiming independent tennis knowledge when it merely reproduces sportsbook prices.

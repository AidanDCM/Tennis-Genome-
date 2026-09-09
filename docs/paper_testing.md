# Forward Paper-Testing Protocol

## Purpose

Historical backtests are necessary but insufficient. Once the first calibrated engine exists, it must produce locked forward predictions before matches begin.

## Daily cycle

1. ingest scheduled matches;
2. freeze prediction cutoff/data timestamp;
3. build time-aware player snapshots;
4. build Match Fingerprints;
5. generate independent model probabilities;
6. calculate uncertainty/disagreement/density;
7. optionally capture market prices at the stated decision time;
8. run policy and output `BET`/`PASS`/`PREDICT_ONLY`;
9. persist immutable prediction record;
10. after completion, append result and evaluation data.

## Prediction lock

After step 9, no model input or probability may be rewritten for that prediction ID.

If an injury/news event appears later, create a new prediction/version only if the policy permits a second decision timestamp; never overwrite the first one.

## What to track

Prediction:
- Brier
- log loss
- calibration
- accuracy
- performance by confidence/coverage

Uncertainty:
- error vs model disagreement
- error vs neighborhood density
- error vs data quality

Market-aware:
- decision-time odds
- no-vig probability
- estimated edge
- EV estimate
- close odds
- CLV
- realized profit/loss
- ROI
- drawdown

## Error decomposition

After each match, classify potential forecast error without immediately changing the model:
- ordinary probabilistic loss
- baseline strength miss
- serve/return miss
- surface/context miss
- injury/availability information miss
- workload/form miss
- out-of-distribution match
- bad data
- model disagreement warning ignored
- market disagreement warning

A 70% prediction losing is not automatically a model failure. Error analysis occurs across repeated calibrated predictions.

## Update cadence

Do not retrain/rewrite after every loss.

Use versioned update cycles with enough new observations to evaluate whether a proposed change generalizes.

Candidate structure:
- daily prediction generation
- weekly data-quality review
- monthly/adequate-sample model review
- scheduled promotion only after validation gates

Exact cadence should depend on match volume and experiment needs.

## Calibration monitor

Maintain rolling and cumulative reliability buckets, for example:
- 50-55%
- 55-60%
- 60-65%
- 65-70%
- 70-75%
- 75-80%
- 80-85%
- 85%+

Bins may later be adaptive. Each must report N and uncertainty.

## Selective prediction monitor

Measure retained performance at multiple coverage levels.

The system should prove whether its own confidence ranking is useful.

If top-confidence predictions do not outperform lower-confidence predictions over sufficient samples, abstention logic needs revision.

## Market-policy monitor

Freeze model probabilities independently, then evaluate many betting policies offline from the same locked predictions.

This lets us change decision thresholds without contaminating the tennis model.

## Minimum interpretation discipline

Two weeks can verify that the operational pipeline works; it cannot establish durable profitability.

Profitability evidence requires meaningful sample size across multiple periods/regimes, with uncertainty, CLV, and out-of-sample behavior reported.

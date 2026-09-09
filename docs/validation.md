# Validation Protocol

## Core rule

All deployability claims are chronological.

Random splits can answer limited diagnostic questions but cannot establish real pre-match performance.

## Walk-forward structure

Generic fold:

```text
TRAIN:      all allowed history through T1
VALIDATE:   T1 -> T2
TEST:       T2 -> T3
```

Then roll forward.

The exact calendar boundaries should reflect data coverage and tour changes, but every fold must preserve time order.

## Nested tuning

Hyperparameters, feature selection, calibration methods, abstention thresholds, and betting-policy thresholds are chosen using training/validation history only.

Final test windows cannot influence those choices.

## Untouched holdout

Reserve a final chronological period that is not inspected during feature/model development.

Before unlocking it, freeze:
- feature registry/version
- preprocessing
- models/hyperparameters
- calibration
- ensemble weights
- confidence construction
- abstention policy
- market decision policy if being tested

## Prediction metrics

### Log loss
Primary probability metric; heavily penalizes confident mistakes.

### Brier score
Mean squared error of probability predictions.

### Calibration
Evaluate:
- reliability diagrams
- calibration intercept/slope where appropriate
- expected/maximum calibration error with cautious binning
- observed win rate in prediction buckets

### Accuracy
Report but do not optimize in isolation.

## Confidence / selective prediction

Construct coverage-risk curves.

For thresholds that retain 100%, 90%, 75%, 50%, 25%, 10% of matches, report:
- log loss
- Brier
- accuracy
- calibration
- N

A valid confidence system should generally improve retained-set quality as coverage falls. Any claimed high-confidence accuracy must state coverage and sample size.

## Subgroup reporting

At minimum:
- ATP vs WTA
- hard/clay/grass
- tournament level
- ranking bands
- favorites vs near-even matches
- data-quality bands
- seasons/time periods

Subgroup results are diagnostics unless pre-registered; do not cherry-pick the best slice as the main claim.

## Statistical uncertainty

Where appropriate use:
- block/bootstrap intervals respecting temporal/player dependence when feasible
- paired bootstrap for model metric differences
- Bayesian posterior intervals for hierarchical models
- multiple-comparison corrections for many candidate tests

Do not interpret tiny metric differences without uncertainty.

## Paired model comparison

For candidate model B vs baseline A, evaluate both on exactly the same chronological match set.

Report:
- delta log loss
- delta Brier
- delta calibration
- delta accuracy
- fraction of folds improved
- subgroup stability
- uncertainty interval for deltas

## Ablation

For best accepted model, remove each family:
- baseline strength
- surface
- serve
- return
- form
- workload/rest
- profile
- genome/neighborhood

This estimates dependence on each family and detects decorative complexity.

## Robustness checks

- alternative reasonable preprocessing
- alternative Elo K/scale within pre-registered search
- different form windows/decays
- missingness handling
- retirement exclusion/inclusion policy
- minimum-match/sample thresholds
- surface categorization
- player-order swap

## Leakage tests

Validation does not proceed unless all automated leakage tests pass.

Required:
- T0 timestamp legality
- no self-match in rolling features
- no future Elo/profile values
- train-only preprocessing
- strictly historical neighbors
- future-append invariant
- market cutoff legality

## Market-aware evaluation

When market layer is introduced, evaluate decisions on prices genuinely available at the stated decision timestamp.

Report:
- no-vig edge distribution
- CLV
- realized ROI
- hit rate
- average odds
- number of bets
- total staked units
- drawdown
- performance by edge/confidence bucket

Never retroactively choose the best available historical price unless that price-selection process could have been executed at the time.

## Model promotion gate

Candidate must:
1. pass leakage/data-quality tests;
2. improve a defined primary objective or a pre-specified conditional objective;
3. survive more than one chronological window;
4. have acceptable calibration;
5. show no unexplained catastrophic subgroup behavior;
6. survive adversarial review;
7. reproduce from manifest/config/commit;
8. improve untouched holdout when finally tested.

If the result is ambiguous, status is `needs_replication`, not accepted.

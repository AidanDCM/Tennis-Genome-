# Predictability Objective

## Central question

Tennis Genome should not begin with an assumed statement such as "tennis is 75% predictable."

The engine must empirically estimate:

> How predictable are professional tennis outcomes using information genuinely available before the match, and under what conditions does predictability materially increase or decrease?

## Overall vs selective predictability

One overall accuracy number is insufficient.

The project should estimate a **predictability/coverage frontier**.

Illustrative structure (numbers intentionally blank):

| Coverage retained | Accuracy | Log loss | Brier | Calibration | N |
|---:|---:|---:|---:|---|---:|
| 100% | | | | | |
| 90% | | | | | |
| 75% | | | | | |
| 50% | | | | | |
| 25% | | | | | |
| 10% | | | | | |

If the confidence system is real, retained performance should improve as low-confidence matches are removed.

## What makes a match predictable?

Potential predictors of forecast reliability are themselves hypotheses:
- model agreement
- historical-neighborhood density
- amount of player history
- data completeness
- size of underlying strength difference
- stability of health/current state
- surface experience
- profile/model consistency
- out-of-distribution distance

The engine should learn which of these actually predicts error.

## Probability calibration

Predictability is not only whether the higher-probability player wins.

A calibrated model should approximately satisfy:
- predictions near 55% win near 55% over adequate samples;
- predictions near 70% win near 70%;
- predictions near 85% win near 85%.

This lets the model know how uncertain it is rather than merely rank competitors.

## Information ladder

Measure what each information family contributes.

Example research decomposition:

```text
ranking
+ Elo
+ surface
+ serve/return
+ recent form
+ player profile
+ workload/rest
+ matchup interactions
+ historical neighborhood
+ later context
```

For every addition report the reduction in out-of-sample uncertainty/error.

A valid result could be that most available predictability is already captured by the first few families. That is useful knowledge, not failure.

## Conditional predictability

Search for stable regions where the model is unusually reliable or unreliable.

Examples to test rather than assume:
- large surface-strength mismatch
- elite returner vs weak second serve
- rapidly improving player vs stale rating
- older player after high workload
- injury comeback
- sparse-history players

The result should be a map of **where the engine understands tennis well and where it does not**.

## Betting connection

High predictability does not equal market value.

The market-aware layer asks a second question:

> Is the sportsbook price materially different from our calibrated probability after accounting for vig and model uncertainty?

Thus the complete objective is:
1. discover predictable structure;
2. estimate probability honestly;
3. identify uncertainty/abstain when appropriate;
4. separately test whether the market misprices any of those situations.

## Success

The project succeeds scientifically even if it discovers a lower ceiling than hoped, provided it can quantify that ceiling honestly and identify which information adds value.

The project succeeds as a betting-decision system only if a separately validated market policy demonstrates robust out-of-sample edge/profitability. That conclusion cannot be assumed in advance.

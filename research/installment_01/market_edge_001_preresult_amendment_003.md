# MARKET-EDGE-001 — Pre-Result Amendment 003

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Purpose

Freeze the remaining chronological fitting, numerical, and multiplicity details for the closing-market incrementality test before any licensed Betfair market result is inspected.

## Evaluation population

Each tour/signal comparison uses only rows that have:

- a deterministic MARKET-HIST-001 match join;
- an executable `CLOSE_PREPLAY` two-way Betfair checkpoint;
- a valid `exchange_mid_implied_proportional_v1` market probability;
- a pre-existing frozen signal value produced without market information;
- a settled non-walkover binary match outcome for evaluation.

The same matched rows are used for the market recalibration control and signal challenger within each claim.

## Chronological fitting

- Evaluation is expanding-year walk-forward.
- Test-year outcomes are never used to fit that year's parameters.
- A test year is eligible only when at least **1,000** earlier matched rows exist for that same tour/signal claim.
- Parameters are refit independently for each test year using only earlier eligible rows.
- Rows within a year are never used to fit another row in that same year.

## Numerical transform

Market probabilities entering the offset model are clipped only for numerical logit evaluation to:

```text
[1e-6, 1 - 1e-6]
```

The unclipped probability remains the reported market probability and is used for ordinary Brier scoring.

If a signal is standardized, mean and population standard deviation are fit on the earlier-year training rows only. A zero/non-finite training standard deviation causes that test year to be ineligible for the signal challenger rather than silently inventing scale.

## Offset logistic fitting

For the market recalibration control:

```text
logit(p_hat) = logit(p_market) + intercept
```

For the signal challenger:

```text
logit(p_hat) = logit(p_market) + intercept + beta * z_signal
```

Parameters minimize mean binary log loss on earlier-year rows.

Optimizer:

- `scipy.optimize.minimize`
- method: `BFGS`
- initial parameter vector: zeros
- gradient supplied analytically
- tolerance: `1e-10`
- maximum iterations: `1000`

A non-successful or non-finite optimizer result fails closed for that evaluation year. No alternate optimizer may be substituted after inspecting results.

## Inference

For each of the four confirmatory claims, challenger-vs-market-recalibration-control inference uses:

- paired percentile bootstrap, 95% confidence interval, **10,000** resamples;
- deterministic bootstrap seed derived from experiment ID + tour + signal + metric;
- paired two-sided sign-flip/randomization test, **20,000** Monte Carlo draws when exact enumeration is not used;
- exact McNemar for classification disagreements as a secondary metric only.

The confirmatory proper-score claim requires the lower endpoint of both Brier and log-loss improvement intervals to exceed zero.

## Year stability

A signal must improve both Brier and log loss versus the recalibration control in at least **60% of eligible evaluation years** and must improve both aggregate proper scores in the predeclared recent diagnostic period **2021-2025** when that period contains eligible rows.

No single year may contribute more than 50% of the total aggregate proper-score improvement magnitude for a promoted claim. If aggregate improvement is non-positive this concentration check is not used to rescue it.

## Multiplicity

The four predeclared confirmatory claims remain:

1. ATP Profile Gap;
2. WTA Profile Gap;
3. ATP Genome;
4. WTA Genome.

For each primary proper-score metric separately, take the raw paired sign-flip p-values for those four claims and apply the Holm step-down family-wise adjustment.

A market-incremental promotion additionally requires Holm-adjusted `p < 0.05` for both Brier and log loss.

Bootstrap intervals remain effect-size uncertainty summaries and are not themselves Holm-adjusted.

## No adaptive rescue

If a signal fails these gates, no alternate minimum-history threshold, clipping bound, optimizer, signal transform, checkpoint, probability transform, tour pooling, or subgroup can replace the failed confirmatory result within MARKET-EDGE-001. Any later hypothesis receives a new preregistration and new experiment ID.

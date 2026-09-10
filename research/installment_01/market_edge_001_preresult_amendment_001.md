# MARKET-EDGE-001 — Pre-Result Amendment 001

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Reason

The original MARKET-EDGE-001 protocol compares pre-existing Tennis Genome signals with the closing Betfair market. Before any licensed MARKET-HIST-001 data have been supplied or inspected, this amendment strengthens the adversarial control so ordinary market miscalibration cannot be mistaken for signal incrementality.

## Closing-market primary comparison

For each tour and each preregistered signal, evaluate three probability views on the exact same chronological out-of-sample rows:

1. **Raw market** — the frozen closing Betfair benchmark probability.
2. **Market recalibration control** — `logit(p_market) + intercept`, where the intercept is fit using strictly earlier years only.
3. **Signal challenger** — `logit(p_market) + intercept + beta * signal`, where intercept and signal coefficient are fit using strictly earlier years only.

The market log-odds coefficient is fixed at 1.0 in both fitted views. This is an offset model, not an unconstrained logistic regression that may relearn the market probability from scratch.

The signal's confirmatory incrementality claim is based on **challenger versus market recalibration control**, not challenger versus raw market.

Raw market scores remain reported because they establish the exchange's absolute calibration/prediction baseline.

## Fitting

- Fit intercept/control and intercept+signal parameters by minimizing binary log loss on earlier-year rows only.
- No current-year or future-year outcomes may enter parameter fitting.
- The first evaluation year must have a declared minimum prior-row count.
- Feature transforms, clipping and optimizer settings are fixed in code before result inspection.
- Signal standardization, if used, must be fit on earlier-year rows only and the fitted scale recorded.

## Promotion gate clarification

A Profile Gap or Genome signal may be called **market-incremental** only if the signal challenger:

1. improves aggregate Brier and log loss versus the paired market recalibration control;
2. has paired bootstrap intervals supporting positive improvement for both proper scores;
3. has a paired sign-flip/permutation robustness result consistent with the improvement;
4. is directionally stable across years and is not driven by one year;
5. survives the already-preregistered Holm family across ATP/WTA x Profile Gap/Genome;
6. satisfies all chronology/identity/source-integrity requirements in the original protocol.

Raw-market comparisons are supporting diagnostics and cannot rescue a failure against the stronger recalibration control.

## Why this is stricter

If the Betfair closing market is slightly under- or over-confident, an augmented model could otherwise appear useful simply by correcting a global intercept/calibration error. Requiring the pre-existing tennis signal to beat a market-only recalibration fitted on identical historical rows isolates the question we actually care about: does the signal contribute information beyond the market itself?

## Unchanged

This amendment does not alter:

- the four confirmatory signal/tour claims;
- Holm multiplicity correction;
- checkpoint definitions;
- Profile Gap or Genome definitions;
- TGE-Independent-v1;
- the prohibition on tuning signals with market outcomes;
- the distinction between closing information tests and executable decision-point tests;
- the non-claim of profitability.

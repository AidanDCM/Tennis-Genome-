# MARKET-EDGE-001 — Pre-Result Amendment 006

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Purpose

Strengthen the primary market-recalibration adversary so ordinary market calibration slope error cannot be mistaken for Profile Gap or Genome incrementality.

## Superseded primary control

Pre-Result Amendment 001 fixed the market-logit coefficient at 1 and fit only an intercept. That protects against global intercept bias but does not protect against overconfidence/underconfidence in the market probability scale.

No licensed MARKET-HIST-001 prices or MARKET-EDGE-001 results have been supplied or inspected. Therefore the primary control is strengthened prospectively before any real result exists.

## New primary chronological models

For each tour and signal, on each evaluation year, fit using strictly earlier matched years only:

### Market recalibration control

```text
logit(p_control) = alpha + gamma * logit(p_market)
```

### Signal challenger

```text
logit(p_challenger) = alpha + gamma * logit(p_market) + beta * z(signal)
```

where `z(signal)` is standardized using the challenger training rows only.

The raw market probability remains an unfitted benchmark and is always reported.

## Primary incrementality claim

The signal's confirmatory proper-score comparison is challenger versus the two-parameter market recalibration control above.

A signal does not earn market-incremental status merely by correcting the market's intercept or probability slope.

## Fitting

- BFGS with analytic gradients and the already-amended stable logistic objective.
- `maxiter = 1000`.
- `gtol = 1e-8`.
- market probabilities clipped only for the logit transform at the already-frozen boundary.
- no current-year or future-year outcomes in fitting.
- no regularization in this low-dimensional primary specification.
- the fitted market slope is recorded for every evaluation row for auditability.

## Diagnostic continuity

The earlier fixed-slope offset specification may be retained only as a non-primary engineering or sensitivity diagnostic. It cannot be used to rescue a claim that fails against the stronger intercept+slope control.

## Unchanged

This amendment does not change:

- the four ATP/WTA × Profile Gap/Genome claims;
- the frozen Profile Gap or Genome signal values;
- the Betfair closing-price probability transform;
- the completed-match-only primary population;
- paired bootstrap, sign-flip and McNemar procedures;
- Holm FWER correction;
- annual/recent/concentration gates;
- the post-2025 prohibition;
- commission/CLV diagnostics;
- TGE-Independent-v1;
- the non-claim of profitability.

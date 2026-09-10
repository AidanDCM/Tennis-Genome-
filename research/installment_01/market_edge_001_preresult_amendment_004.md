# MARKET-EDGE-001 — Pre-Result Amendment 004

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Trigger

The first synthetic implementation gate for the offset-logistic evaluator failed before any licensed Betfair files or market outcomes were supplied. SciPy BFGS reached a numerically stationary solution but returned `Desired error not necessarily achieved due to precision loss` under the `1e-10` tolerance registered in Amendment 003.

This is an engineering/numerical amendment made from synthetic data only. It does not respond to any MARKET-EDGE-001 scientific result.

## Revised optimizer specification

The optimizer remains:

- `scipy.optimize.minimize`;
- method `BFGS`;
- zero initialization;
- analytic gradient;
- maximum iterations `1000`.

The convergence criterion is revised to:

- BFGS option `gtol=1e-8`;
- no separate generic `tol` argument.

The objective must use a numerically stable binary logistic negative-log-likelihood, equivalent to:

```text
mean(logaddexp(0, linear_predictor) - y * linear_predictor)
```

Prediction uses a numerically stable sigmoid implementation.

A fit remains ineligible if BFGS does not report success or if fitted parameters/objective/gradient contain non-finite values. No alternate optimizer or tolerance may be selected after licensed market results are inspected.

## Unchanged

All chronology, market-offset, signal-standardization, minimum-history, inference, yearly-stability, concentration, multiplicity, and promotion gates from the previous MARKET-EDGE-001 documents remain unchanged.

# GENOME-NN-001 Pre-result Amendment 002

Status: **frozen before historical GENOME-NN-001 output is inspected**

This amendment makes the shared-player adversarial classification and diagnostic bucketing fully mechanical.

## Shared-player exclusion predictive sensitivity

For every target where 100 historical neighbors remain after excluding any candidate sharing either target player, store `R_NN_no_shared`.

Run the **same expanding-year fair meta comparison** used by the primary experiment, but restricted to rows for which `R_NN_no_shared` exists:

- sensitivity meta-control: standardized `[logit(p_core_F)]`;
- sensitivity challenger: standardized `[logit(p_core_F), R_NN_no_shared]`;
- same `LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)`;
- same minimum prior meta-training population of 1,000 rows;
- training uses only earlier years;
- scoring uses exactly the same target rows for control and challenger.

Report:
- eligible sensitivity rows / primary neighbor rows;
- sensitivity coverage;
- aggregate Brier/log-loss deltas;
- 2021–2025 deltas;
- annual joint-win rate;
- residual slope and Q5-minus-Q1 using `R_NN_no_shared`.

### Classification

If the primary H-011 gate passes:

- **general historical-alignment candidate** requires shared-player sensitivity coverage `>= 80%` **and** positive aggregate Brier and log-loss improvement under exclusion;
- if coverage is `>= 80%` but either aggregate proper-score improvement is non-positive, classify the positive primary result **identity-dependent / conditional**;
- if coverage is `< 80%`, classify transferability **inconclusive** rather than general, regardless of the direction on the smaller sensitivity population.

The sensitivity cannot upgrade a failed primary k=100 result.

## Equal-count bucketing

For neighbor-residual and density quintiles:
- sort by `(diagnostic_value, match_id)`;
- assign equal-count rank buckets 1 through 5 using deterministic integer rank;
- bucket 1 is the lowest value, bucket 5 the highest.

## Per-match density error

For H-012:
- raw-Core Brier contribution is `(p_core_F - y_F)^2`;
- raw-Core log-loss contribution uses numerical clipping only at `[1e-15, 1 - 1e-15]`;
- absolute residual is `abs(y_F - p_core_F)`.

## Secondary k residual diagnostics

For k in `{25, 100, 250}`, report only:
- N;
- slope of realized Core residual on neighbor residual mean;
- Q5-minus-Q1 realized Core residual.

Only k=100 controls H-011/H-012 promotion status.

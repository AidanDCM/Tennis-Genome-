# GENOME-NN-001 Pre-result Amendment 001

Status: **frozen before historical GENOME-NN-001 output is inspected**

This amendment clarifies implementation details that were not explicit enough in the original protocol. It does not change the primary representation, k=100, distance metric, outcomes, or promotion gates.

## Meta-model scaling

The fair meta-control and Genome challenger both use a training-only `StandardScaler` before the preregistered L2 logistic regression.

For target year `Y`:
- fit the scaler only on earlier out-of-sample rows that already possess legal historical neighbor summaries;
- fit the meta-control on standardized `[logit(p_core_F)]`;
- fit the challenger on standardized `[logit(p_core_F), R_NN]`;
- use separate scalers/pipelines for control and challenger;
- no target-year feature or outcome may influence scaling.

Reason: `R_NN` naturally lives on a much smaller numerical scale than Core log-odds. Without standardization, `C=1.0` would regularize the two coordinates differently for unit-scale reasons unrelated to predictive information.

Estimator remains:
- `LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)`;
- intercept enabled;
- no class weighting.

## Core logit numerical clipping

When converting Core probability to a logit for the meta-model only, clip numerical probability to `[1e-9, 1 - 1e-9]` before taking the logit. Raw Core probabilities used for scoring remain unchanged.

## Candidate retrieval for deterministic k and shared-player sensitivity

The historical index may retrieve up to the nearest **1,000** candidates in one search operation so that:
- primary k=100;
- diagnostics k=25 and k=250;
- and the k=100 shared-player-exclusion sensitivity

can all be selected from the same deterministic distance ordering.

Candidate rows are ordered by `(distance, match_id)` after retrieval.

If the historical pool contains fewer than 1,000 rows, use the entire available pool. A target is eligible for the primary analysis only when at least 100 historical rows exist; the experiment-level historical pool gate remains 1,000 rows.

For shared-player exclusion, discard candidates sharing either target player, then take the first 100. If fewer than 100 remain among the retrieved candidates, omit that target from the exclusion sensitivity only. Primary results remain unchanged.

## Secondary k outputs

k=25 and k=250 are diagnostic-only residual/density summaries. They do not receive separate promotion gates and cannot replace k=100 after results are seen.

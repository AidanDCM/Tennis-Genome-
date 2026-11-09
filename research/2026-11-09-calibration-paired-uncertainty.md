# 2026-11-09 Iteration 4 — paired uncertainty and fixed-slope control

Evidence tier: research-only WTA Web Shadow; no independent forward challenger settlement, no production model modification or promotion.

## Baseline and integrity audit
- Main SHA 8af76720a6291b166263fa1cd8191504f84ed6b6. Main scorecard: 88 settled, 85 scored completed, 46/85 correct (54.12%), Brier 0.25146106, log loss 0.69690827, 16 pending.
- Open PR #428 (result acquisition) still has action_required CI and two identity conflicts. Open draft PR #429 is isolated calibration research.
- Previous CI on PR #429 head 1a5509d49a2f5b434873c541977f314dcbb633d7 passed (run 42685720624; Ruff and Pytest successful). Prior research workflow 42685655265 passed.
- Latest forward aggregate run 42655914939 reported zero settled forward challenger observations. This paper-only experiment is NOT evidence of champion–challenger forward improvement.

## Implemented this iteration
- Commit b3a71e8c93c63174a8deb280c8f0add86c6e8dc7: add paired Brier/log-loss per-match differences with descriptive unadjusted normal-approximation 95% intervals, and a fixed positive 0.5-slope shrinkage control. The baseline, original walk-forward training logic, immutable predictions and champion are unchanged.
- Commit 0c32a3f31c237e1371cd5005563d5413786ce4dc: add four tests for zero differences, non-finite inputs, shrinkage direction and preventing unobserved-result leakage.
- Research-only workflow 42694781390 completed SUCCESS on implementation commit b3a71e8c93c63174a8deb280c8f0add86c6e8dc7. Exact-head CI for final test commit 0c32a3f31c237e1371cd5005563d5413786ce4dc: run 42694817469 (check final status before asserting pass). Earlier implementation-only CI 42694787898 also initiated.

## Interpretation and falsification
Earlier 55 paper-match walk-forward result (26/55 correct) improved Brier from 0.263800 to 0.258233 and log loss from 0.722770 to 0.710449; it did NOT improve winner hit rate. New paired intervals quantify descriptive uncertainty only. Inference may be optimistic because matches are temporally dependent, the model was selected after seeing paper-scorecard performance, and the sample is small. A fixed shrinkage control checks whether adaptively selected slopes are doing anything beyond generic confidence reduction; it is not a truly null treatment. Reject any claim of prospective superiority without a locked independent sample.

## Research comparison
Diebold and Mariano (1995), https://doi.org/10.1080/07350015.1995.10524599, compares paired forecast loss with serial correlation. Coroneo and Iacone (2020), https://doi.org/10.1002/jae.2756, finds conventional small-sample predictive-ability tests can be poorly sized. Bank of England's implementation https://bank-of-england.github.io/forecast_evaluation/api/tests.html applies HAC standard errors and a small-sample correction. Our unadjusted intervals are a diagnostic first step, NOT a formal dependence-adjusted hypothesis test.

## Next executable actions
1. Inspect exact-head CI 42694817469, fix failures and rerun until green.
2. Download/read workflow result artifact for exact paired intervals and fixed-control performance, document all values and whether intervals span zero; do not infer significance without dependence-aware intervals.
3. Implement cluster-by-slate/block bootstrap or predeclared HAC uncertainty and test with synthetic correlated observations.
4. Resolve #428 identity conflicts with independent sources without overriding trust gates; increase prospective settled N.
5. Compare surface-specific/recency Elo or feature ablations only on temporally valid, sufficiently complete inputs.

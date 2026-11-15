# PR #458 exact-head CI verification — 2026-11-12

## Hypothesis and acceptance
Hypothesis: the fail-closed WTA acquisition guard introduced in draft PR #458 passes CI and rejects failed/skipped/indeterminate proposal-gate outputs without weakening the successful-allowed path. Baseline: main `8af76720a6291b166263fa1cd8191504f84ed6b6`; proposed head `f5ca0cdc5333bb3242b024c55b867c6aa7bf5087`. Acceptance: exact-head associated CI success, Ruff and pytest job steps successful, all ten guards present, no old fail-open guard, and five prespecified control-flow states correct. This is an operational safety audit, not a forecasting improvement.

## Executed evidence
- [Draft PR #458](https://github.com/AidanDCM/Tennis-Genome-/pull/458) remains open, unmerged, based on main and dependent on draft PR #457.
- [Exact-head CI run #43163081105](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43163081105) returned completed/success for PR #458 head. Job 130998575937: Ruff success, Pytest success, diagnostic artifact upload success; "Enforce checks" skipped. Exact pytest count and artifact contents were not downloaded or independently verified.
- Fetched [workflow at PR #458 branch](https://github.com/AidanDCM/Tennis-Genome-/blob/f5ca0cdc5333bb3242b024c55b867c6aa7bf5087/.github/workflows/wta_web_shadow_results.yml), blob `f49387bb740a664ef5a72ee850203301062dbf2a`, and [regression test](https://github.com/AidanDCM/Tennis-Genome-/blob/f5ca0cdc5333bb3242b024c55b867c6aa7bf5087/tests/test_web_shadow_wta_results_workflow.py), blob `7338d95e202f6bf577906621dd815e4449cf55db`.
- Executed a deterministic JS check against fetched workflow text: ten exact guards `steps.pr_gate.outcome == 'success' && steps.pr_gate.outputs.blocked == 'false'`, zero old `blocked != 'true'` guards. Truth-table cases: (success,true) reject; (success,false) allow; (failure,empty) reject; (skipped,empty) reject; (success,empty) reject. All five matched expectation. Static test does not simulate GitHub Actions runtime.
- [PR #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) remains open and unmerged: one proposed Chennai result, 13 unresolved predictions, two excluded identity conflicts. No settlement authorized.
- Main [non-production WTA scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/web-shadow/scorecard.json): 85 eligible, 46 correct, Brier 0.2514610585, log loss 0.6969082733, 16 pending, `production_eligible=false`. Production-forward denominator and immutable champion checksum not independently verified.

## Research / contrary evidence
- Manokhin and Grønhaug (2026-01-19), [Classifier Calibration at Scale](https://arxiv.org/abs/2601.19944): randomized stratified cross-validation on tabular binary tasks, with separate calibration folds; some Platt/isotonic calibrations degrade proper scores. Non-chronological and non-tennis, so not a directly comparable benchmark; implementation license not verified; no code adopted.
- Waghmare and Ziegel (2026), [Proper Scoring Rules for Estimation and Forecast Evaluation](https://doi.org/10.1146/annurev-statistics-042424-050626): proper-scoring review, CC BY 4.0, useful for Brier/log loss definitions but not tennis performance evidence.

## Negative findings and queue
1. CI passed but no direct workflow-dispatch runtime test of the blocked/failure/allowed gate paths was executed; source-text regression alone cannot establish full Actions semantics.
2. PR #458 depends on PR #457; do not merge either automatically. Human review and explicit safe integration required.
3. PR #428 blocks new acquisition while its evidence is reviewed; preserve all exclusions and pre-start provenance.
4. Next: download exact-head CI diagnostic artifact to verify pytest counts; add isolated behavioral guard tests if safe; review Chennai result evidence and resolve proposal safely; verify production champion checksum and forward denominators; then accumulate newly locked prospective observations for paired Elo/fixed-0.5 evaluation with an untouched holdout.

# 2026-11-12 WTA acquisition gate synthetic contract iteration

## Evidence and preregistration
- Baseline main `8af76720a6291b166263fa1cd8191504f84ed6b6`; existing safety PR [#458](https://github.com/AidanDCM/Tennis-Genome-/pull/458), head `f5ca0cdc5333bb3242b024c55b867c6aa7bf5087`. This branch is based on #458, **not** on main.
- Current main workflow blob `2a698a6f56297aee054a94dc49a28fefaaff2d35` retains fail-open `blocked != 'true'` conditions; PR #458 fixes them. Main active results blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` lists only Hong Kong result. [PR #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) is still the proposed Chennai result blocker.
- Hypothesis: PR #458's ten guards admit downstream acquisition only when gate outcome is `success` and blocked output is `false`. Baseline: main's `blocked != 'true'` admits empty output on failed/skipped gate. Prespecified pass: all nine synthetic gate-state combinations and four critical step-source guards pass; no safety exclusions weakened. Fail if any unintended state proceeds.
- Exact test: `python -m pytest -q tests/test_wta_gate_behavior_contract.py`; optional `python -m ruff check tests/test_wta_gate_behavior_contract.py`. The synthetic test is **not** a GitHub Actions runtime integration test.

## Executed evidence
- Local independent proof-of-concept test with a manually transcribed representative guard fixture: `python -m pytest -q test_gate_contract.py` -> **2 passed in 0.08s**. This local fixture is not the actual fetched GitHub file, so it is not evidence of PR exact-head behavior.
- GitHub connector created branch from #458 head and committed `tests/test_wta_gate_behavior_contract.py` at `e550f13144581689063ba0fc60635ca82bc9e148`. Exact-head CI is pending inspection.
- No production settlement, forecast, identity, or champion change. No model accuracy claim. The current main non-production WTA scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb` has 85 eligible scored matches, 46 correct, Brier 0.251461, log loss 0.696908, 16 pending; it is not qualified production-forward evidence. Champion checksum and qualified forward N not independently verified this run.

## Research and contrary evidence
- Waghmare and Ziegel (2026), [Proper Scoring Rules for Estimation and Forecast Evaluation](https://doi.org/10.1146/annurev-statistics-042424-050626), CC BY 4.0 review, discusses proper-score evaluation and uncertainty; methodological only, no tennis reproduction.
- Frazier and Poskitt (2025), [Sequential Scoring Rule Evaluation for Forecast Method Selection](https://arxiv.org/abs/2505.09090), proposes sequential comparison controls in simulation; not tested here, license not verified. A reminder that repeated challenger comparisons need sequential error control.
- Contrary caution: Ferro (2017), [Measuring forecast performance in the presence of observation error](https://doi.org/10.1002/qj.3115), warns that noisy labels can reverse forecast rankings. No code imported; none of these populations licenses direct transfer of performance claims to WTA.

## Negative results, limits, and next executable queue
1. **Highest:** run exact-head CI for this PR, inspect Ruff/pytest output; repair if failed. Test actual blocked, failed and allowed workflow branches in isolated GitHub Actions with no settlement writes.
2. Review #428 immutable Chennai evidence and verify identity/source/timing before human settlement decision; never bypass conflicts LS031/LS020.
3. Refresh immutable champion hash, verified forward settlements and capture coverage independently from main.
4. Accumulate genuinely locked prospective paired observations, compare frozen champion vs fixed-0.5 and Elo using chronological Brier/log loss, calibration, accuracy Wilson interval, tour/surface/coverage and paired uncertainty. Preserve untouched final holdout and multiplicity budget.

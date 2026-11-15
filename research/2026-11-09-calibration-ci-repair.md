# 2026-11-09 research iteration: calibration CI repair (non-production)

Evidence tier: software quality gate, not new tennis prediction accuracy. Main remains at 8af76720a6291b166263fa1cd8191504f84ed6b6; PR #429 is an isolated research challenger and PR #428 remains unresolved. Frozen champion and all pre-start predictions untouched.

## Exact diagnosis
- Earlier research PR CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42676681616 failed at Ruff, not pytest.
- CI log: 10 Ruff violations in scripts/research_web_shadow_calibration.py (B905 zip strict, E501 line length, UP017 datetime.UTC). Pytest: 1308 passed, 2 warnings.
- Research experiment workflow https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42676595311 previously succeeded; this does not override the failed repository-wide lint gate.

## Executed repair
- Updated only scripts/research_web_shadow_calibration.py on research/2026-11-09-calibration-audit.
- Added strict=True to parallel zip calls; replaced timezone.utc with datetime.UTC; wrapped long lines without changing calibration algorithm, training/evaluation membership or data artifacts.
- Commits 8f9e6d914c94cc381d9060a32a141650375fef68 and 583ffc60e406b3a981a18179d624d38a882f0adc.
- GitHub triggered exact-head research workflow https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42685655265 and exact-head CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42685660042. Both pending at ledger creation; check conclusions and job diagnostics, do not assert green until confirmed.

## Research cross-check
Gneiting & Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation: https://doi.org/10.1198/016214506000001437. Proper scores, including Brier and log loss, are necessary alongside winner hit rate to assess probability calibration. Gneiting, Balabdaoui & Raftery (2007), https://doi.org/10.1111/j.1467-9868.2007.00587.x, emphasizes sharpness conditional on calibration. These methodological sources are not tennis-specific validation.

## Current performance and blockers
Non-production WTA Web Shadow main scorecard: 85 scored completed of 88 settled, 46/85 correct (54.12%), Brier 0.251461, log loss 0.696908. Earlier chronological calibration ablation evaluated 55 reused paper outcomes: original Brier 0.263800 vs adjusted 0.258233; log loss 0.722770 vs 0.710449; winner selections unchanged 26/55. This is exploratory and not independent forward challenger validation. Latest verified forward aggregate run 42655914939 had 0 settled challenger observations. PR #428 includes unresolved identity conflicts and action_required CI.

## Next executable tasks
1. Inspect exact-head CI 42685660042 and research 42685655265; fix remaining issues and verify passing tests.
2. Add paired uncertainty intervals, chronology leakage tests, and a fixed 0.5-shrinkage negative control to the research script; preserve independent holdout.
3. Resolve PR #428 identity conflicts using source-backed evidence without weakening gates; increase genuinely qualified forward settlement N.
4. Run a preregistered surface/recency Elo ablation only after data completeness and temporal availability audits.

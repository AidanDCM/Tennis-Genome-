# Iteration 20 — 2026-11-10: make date-cluster sensitivity output auditable

Status: research-only; no production model, scorecard, prediction, settlement, or champion changed.

## Source / execution evidence
- Main at PR base: `8af76720a6291b166263fa1cd8191504f84ed6b6` (PR metadata, verify against live main before any merge).
- Draft research PR #429 head before this run: `3b9041dba514eed60339f415128440ecc8dbcd63`; acquisition PR #428 remains open, head `e676c961d674ffd32d254bb96f738ae7242e211f`.
- CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42810036567: actual job `129808861364`, completed success; Ruff and Pytest steps passed. This verifies tests, **not** numerical experiment output.
- Existing research source blob `611daf2912a5c7fdb19e9405cccafea487a68e5b`; test blob `0148c013084e98cf70b7bafbd6ea6eddc451a2e7`; workflow before update blob `4f8e5f7a0e4632d0fa995d353eee0afc83623019`.
- Workflow-only change `b8939652a6364f796b05c5711cafda1454e4e921`: tee the complete read-only experiment JSON into `date-cluster-sensitivity.json` and upload as named CI artifact. No CI run returned for that commit at initial check; numerical values **not yet verified**.
- Local direct git fetch attempted: `git ls-remote https://github.com/AidanDCM/Tennis-Genome-.git HEAD`; blocked by DNS `Could not resolve host: github.com`. GitHub connector reads and writes succeeded.
- Reproduce when repository available: `python scripts/research_calibration_signflip_real.py --repo-root . > date-cluster-sensitivity.json`; `pytest -q tests/test_research_calibration_signflip_real.py`; `ruff check .`. Compare artifact JSON to 55 evaluation IDs and 15 UTC date clusters.

## Preregistered comparison / limits
Hypothesis: fixed slope 0.5 retains positive paired Brier and log-loss improvement against frozen slope 1.0 after each of 15 leave-one-UTC-start-date exclusions. Adaptive chronological slope is a secondary control. Population: the 55 historical scored WTA paper observations (evaluation IDs emitted by script); no independent final holdout is touched. Pass sensitivity criterion: all 15 exclusions positive for both scores; fail if any zero/negative. Report min/max, reversals and influential dates, not just a favorable aggregate. This is *influence analysis*, not leave-one-cluster-out retraining or confirmatory inference. Existing regression tests cover 55 IDs, 15 dates, 85 completed of 88 settlements. Numerical results await actual script run.

## Independent evidence / operational blockers
Non-production WTA Web Shadow historical 46/85 = 54.12% winner accuracy, Brier 0.251461, log loss 0.696908; 88 settled records include 3 non-completed. Do not call these prospective challenger results. Last documented independent forward challenger aggregate: zero; not freshly reverified this run. PR #428 snapshot: 16 pending, one captured finished result, 13 unmatched, two player-identity conflicts; never override identity/provenance gates to increase N.

## Research and contrary evidence
- Qiu et al. (2024), https://arxiv.org/abs/2405.20400, cluster-aware validation / NICc for fitted models; theoretical and simulation work, not a tennis benchmark; our fixed-prediction date deletion is weaker than refitting cluster CV. No code copied, implementation/license not assessed.
- Pic et al. (2025), https://doi.org/10.5194/ascmo-11-23-2025, proper scoring rules emphasize complementary diagnostics; atmospheric multivariate setting, not comparable tennis populations; do not optimize one score alone. No code copied.
- NOAA weather clustering study (2024), https://doi.org/10.1175/WAF-D-23-0017.1, cluster choices can alter forecast comparisons; domain mismatch prevents transferring performance estimates. No code copied.

## Priority queue
P0: verify exact-head CI for artifact commit, retrieve complete 15-date JSON, report all exclusions and negative cases; if no run, inspect branch workflow activation/permissions before modifying more code.
P0: audit main's latest forward settlement and source identity gates, then investigate PR #428's two conflicts with provider IDs and raw SHA evidence.
P1: independent chronological prospective paired champion/challenger evaluation with locked forecasts, Brier/log loss, confidence intervals, coverage, calibration and surface/tour strata.
P2: simple Elo/surface ablation only after sufficient qualified forward observations; preserve untouched holdout.

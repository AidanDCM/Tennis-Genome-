# Iteration 9 — repair end-to-end research CI (2026-11-09)

Status: **research-only engineering repair; no validated forecasting improvement, no champion change.**

## Reproducible failure and repair
- Source: PR #429 research branch, exact failing head `9362d43bc7f8f092822351913831d5409dcb8d1d`.
- CI failure run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42729968729
- Inspected job `129545212195` logs. Ruff reported `I001` in `tests/test_research_calibration_signflip_real.py:6`. Pytest collection raised `ModuleNotFoundError: No module named 'research_cluster_sign_flip'` when the new test imported the script as a package module. No tests were executed because collection aborted.
- Repair commit `f8001d896a21808cc75a23d4d0da169a8d3384a3`: support both package-import and direct-script execution using conditional imports; no data or model changes.
- Repair commit `1c67d130b69ed227973261d9aa643c00c57c6d10`: group test imports consistently for Ruff.
- Reproduce: `ruff check . && pytest -q tests/test_research_calibration_signflip_real.py && pytest -q`; separately `python scripts/research_calibration_signflip_real.py --repo-root .`.
- CI at the time of ledger writing was triggered for the first repair; **exact-head CI for the second repair is not yet verified**. Do not report these seven tests as passing until exact-head CI completes.

## Evidence tier and negative findings
- Immutable champion unchanged. Non-production WTA Web Shadow has 88 settled records, 85 completed/scored, 46 correct (54.12%), Brier 0.251461, log loss 0.696908. Independent forward challenger settled N remains last verified as **zero**; reconfirm aggregate before claiming a newer number.
- Exploratory calibration sign-flip diagnostic: 55 WTA matches, 15 UTC-date clusters, adaptive Brier improvement +0.00557 and fixed-half +0.01089. Exact two-sided sign-flip fractions 0.3297 and 0.2145; neither confirmatory. Historical observations reused across studies; no model promotion.
- Open result-acquisition PR #428 has two unresolved player-identity conflicts. Do not relax identity or pre-start evidence gates.

## External method check
- MacKinnon, Nielsen & Webb (2023), *Fast and reliable jackknife and bootstrap methods for cluster-robust inference*, Journal of Applied Econometrics, https://doi.org/10.1002/jae.2969. Open-access paper, simulation and three empirical examples; data archived https://doi.org/10.15456/jae.2023042.1653281787. It finds few/unbalanced clusters can make conventional inference unreliable. Applicability: examine cluster influence, but regression-specific bootstrap claims do not transfer automatically to our paired forecast-loss differences. No paper code copied.
- MacKinnon, Nielsen & Webb (2023), *Testing for the appropriate level of clustering in linear regression models*, https://doi.org/10.1016/j.jeconom.2023.03.005. Open access; simulation-based clustering choice. A fixed UTC-date grouping is not inherently correct; sensitivity to tournament groupings is needed. No paper code copied.

## Next executable work
1. Inspect exact-head CI after both fixes; repair any failures.
2. Run the seven real-scorecard regression tests and sign-flip experiment in GitHub Actions.
3. Implement leave-one-date/tournament-out influence diagnostics and quantify which clusters drive apparent calibration improvement, without tuning on the evaluation set.
4. Audit #428 identity conflicts and forward settlement capture before increasing model complexity.

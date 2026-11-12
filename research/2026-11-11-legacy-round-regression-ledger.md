# Iteration 36 — legacy WTA round fail-closed regression (2026-11-11 UTC)

## Hypothesis and preregistration
H1: the current legacy (non-official MatchID) result matcher rejects incorrect numeric/textual round IDs, incorrect full player identities and duplicate pair+round matches, while exact official MatchID matching tolerates a round discrepancy **only** when player identities agree. Baseline: current main code; challenger: no model change, test-only safety regression. Success: all new parameterized pytest cases pass on exact PR head, with no production files changed. Failure: any case fails; do not change matching logic or promote/settle observations without official-source proof.

## Inputs and reproducibility
- Main code: scripts/web_shadow_wta_result_core.py, Git blob `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`.
- Main scorecard: web-shadow/scorecard.json, Git blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`.
- Main active-results: web-shadow/active-results.json, Git blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`.
- Acquisition workflow: .github/workflows/wta_web_shadow_results.yml, Git blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`. It checks out main and blocks if a result PR exists.
- Test population: synthetic fixture LS001/LS002, group 1024/year 2026, Alpha One/Beta Two. **No actual match winners, no historical records and no holdout used.**
- Commands: `python -m pytest -q tests/test_wta_legacy_round_fail_closed_regression.py`; `python -m pytest -q tests/test_web_shadow_wta_results.py`; `ruff check tests/test_wta_legacy_round_fail_closed_regression.py`.
- Test-only branch: `research/2026-11-11-legacy-round-fail-closed-regression`; initial test commit `1e30b4ac5fd54dfa7f1b368b5ed17f426b9cf947`. CI must be associated with the final head.

## Observations and limitations
The inspected source requires a pair+round match for legacy IDs, while exact official IDs require a unique MatchID and exact normalized player pair, retaining a round discrepancy in evidence. The new tests protect that behavior, including nine unsupported legacy round aliases/values, duplicate source rows and player mismatch. These are **regression tests, not a correction to official round semantics**. Exact-head CI pending at initial write. Local checkout unavailable in this runtime: `git clone --depth 1 https://github.com/AidanDCM/Tennis-Genome-.git` failed with `Could not resolve host: github.com`. GitHub connector read/write worked.

## Research comparison
Waghmare & Ziegel, *Proper Scoring Rules for Estimation and Forecast Evaluation*, Annual Review of Statistics and Its Application 13 (2026), https://doi.org/10.1146/annurev-statistics-042424-050626 (first online Nov 13 2025; CC BY 4.0). Proper scores are appropriate for matched prospective binary outcomes, not unresolved observations. Pic et al., *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, 2025, https://doi.org/10.5194/ascmo-11-23-2025 (CC BY 4.0; simulations and wind-speed case study; public R code). Contrarian lesson: scoring improvements do not repair unreliable match identities. Neither paper supplies comparable tennis win rates. No external code copied.

## Evidence tier and negative findings
Non-production WTA Web Shadow historical scorecard: 46/85 winner accuracy 54.12%, Brier 0.251461, log loss 0.696908; matched 78-match Elo baseline 41/78 versus 42/78 accuracy, with descriptive Genome Brier 0.252433 versus Elo 0.259745. Not a new chronological evaluation. No newly verified qualified prospective observations this run. Champion untouched; no results settled. Outstanding result PR #428 blocks fresh collection. Legacy provider RoundID meanings not independently proven; third-party round-ID schemes are **not interchangeable** with the official WTA feed.

## Priority queue
1. Review PR #428's retained source and human-disposition pathway without bypassing gate.
2. Validate numeric RoundID semantics against official retained WTA draw brackets with stable IDs and round positions; require negative controls.
3. Audit original prediction input manifests for the two flagged schedule-source provenance issues.
4. Run end-to-end blocked-acquisition receipt check on PR #430; confirm artifact and no mutations.
5. Accumulate new locked prospective outcomes, then paired champion–challenger Brier/log loss with chronological splits, coverage and calibration; untouched final holdout.

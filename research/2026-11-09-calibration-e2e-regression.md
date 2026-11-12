# Research iteration 8 — end-to-end statistical reproducibility

Date: 2026-11-09. Scope: non-production WTA Web Shadow only. No champion changes.

## Verified repository state
- Main remains unchanged at `8af76720a6291b166263fa1cd8191504f84ed6b6` in the latest verified prior audit.
- Open PRs #428 (result capture, identity conflicts) and #429 (research only).
- Previous exact-head CI run 42722119262 for `6b0323bb8679c68e4f539a9fa47e402386c6e119`: **success**, including Ruff and Pytest.
- Prior CI run 42714833616 for seven sign-flip unit tests: **success**.
- Main non-production paper scorecard: 88 settled, 85 completed scored, 46/85 correct, Brier 0.2514610585, log loss 0.6969082733, 16 pending. These are **not** prospective champion-challenger observations.
- Most recently verified forward challenger settlement count: zero; needs recheck before any claim of an increase.

## Work executed
Added `tests/test_research_calibration_signflip_real.py` in commit `b2c5a776fe72043f3cdfdedede133b94cac074cc`. This executes `evaluate(ROOT)` against the repository's actual 85 completed scorecard records rather than synthetic fixtures. Assertions cover 55 chronologically evaluated matches, 15 UTC-date clusters, 32,768 exact sign configurations for each of four comparisons, valid output ranges, immutable non-production status, 88 total settled statuses, unique evaluation IDs, and the previously measured fixed-half Brier improvement. It is a regression guard, **not** an independent performance claim.

Reproduce with:
```bash
pytest -q tests/test_research_calibration_signflip_real.py
python scripts/research_calibration_signflip_real.py --repo-root .
```
GitHub CI exact-head run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42729919849 (in progress when this ledger was written; do not mark passed until conclusion success).

## Research and interpretation
MacKinnon, Nielsen & Webb (2023), *Fast and reliable jackknife and bootstrap methods for cluster-robust inference*, https://doi.org/10.1002/jae.2969, reports that few and unbalanced clusters undermine conventional confidence intervals; simulations and data openly linked in paper. Transferable: inspect leverage, cluster balance and influence before trusting date-cluster intervals. No external performance number is transferable to WTA.

Earlier observed sign-flip sensitivity fractions (reused retrospective sample): adaptive Brier 0.3297, fixed-half Brier 0.2145, adaptive log loss 0.3307, fixed-half log loss 0.2189. All are **exploratory**, conditional on unverified cluster sign-exchangeability; 131,072 enumerations are not 131,072 tennis observations. Neither challenger earns promotion. Retain the negative result.

## Next executable priorities
1. Verify CI 42729919849 at exact head, fix test failures if any.
2. Add a tournament-cluster and leave-one-cluster-out influence diagnostic; do not treat alternative clustering as a new independent sample or hunt for significance.
3. Unblock PR #428's player identity conflicts with corroborated records and preserve pre-start/result provenance.
4. Acquire genuinely new locked, independently settled forward challenger predictions before interpreting any calibration benefit as generalizable.

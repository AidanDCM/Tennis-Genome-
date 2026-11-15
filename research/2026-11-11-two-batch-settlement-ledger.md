# 2026-11-11 — two-distinct-batch settlement durability (Iteration 43)

## Prespecified test
H1: Applying two independent synthetic Web Shadow settlement batches preserves both settlement records, receipts and metric contributions; replay of either batch fails without mutation. H0: a second batch loses earlier evidence or replay changes scorecard. Pass requires 2 settled / 0 pending / 2 eligible, unchanged first settlement and receipt bytes, distinct run IDs 9001/9002, distinct artifact IDs 7001/7002, and both replays rejected. No model evaluation or production settlement is authorized.

## Source / reproducibility
Main baseline SHA: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
Test file: `tests/test_apply_web_shadow_settlement_batch.py`, original blob `1e0b489d9685451ddb9bd4ac3329e245f0628e26`.
Research branch: `research/2026-11-11-two-batch-settlement-replay`.
Implementation commit before ledger: `5879b30093f94a1ab4701e98b7553cc7bbcae63a`.
Reproduce: `python -m pytest -q tests/test_apply_web_shadow_settlement_batch.py`; `ruff check tests/test_apply_web_shadow_settlement_batch.py`.
Synthetic IDs: `test-slate` / `web:wta:test:1`, `test-slate-2` / `web:wta:test:2`; independent ZIPs, result paths and workflow IDs.

## Actual execution / limitations
GitHub connector fetched source and committed test code; local `git clone --depth 1 --branch research/2026-11-11-two-batch-settlement-replay https://github.com/AidanDCM/Tennis-Genome-.git` failed with `Could not resolve host: github.com`. No local pytest pass claimed. Exact-head GitHub CI must be inspected. PR: https://github.com/AidanDCM/Tennis-Genome-/pull/441. The experiment is a synthetic lifecycle test, not prospective forecasting evidence. Existing historical scorecard: 88 settled, 85 eligible, 46 correct, Brier 0.251461, log loss 0.696908, 16 pending; non-production only.

## Research and contrary evidence
Pagano et al. (2024), *Challenges of Operational Weather Forecast Verification and Evaluation*, DOI https://doi.org/10.1175/BAMS-D-22-0257.1, operational verification review, not tennis; observation coverage and verification workflows transferable, but not accuracy. Bonavita (2024), *On Some Limitations of Current Machine Learning Weather Prediction Models*, DOI https://doi.org/10.1029/2023GL107377, open-access weather model evaluation: strong aggregate scores can mask fidelity failures; supports robustness and failure-mode tests, not direct cross-sport model comparison. No external code or data imported; reuse licenses not required.

## Queue
1. Inspect exact-head CI; debug and retry if red.
2. Check two-batch replay on CI and inspect test logs, not just status.
3. Audit publication invocation and unblock acquisition PR #428 under review; no automatic merge.
4. Independently verify official round IDs and prohibited provenance before legacy settlement.
5. Only after sufficient newly locked prospective observations, compare frozen champion against simple Elo with paired Brier/log loss, chronological strata, calibration and confidence intervals; untouched holdout.

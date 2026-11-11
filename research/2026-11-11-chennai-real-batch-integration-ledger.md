# 2026-11-11 — Chennai settlement real-function CI experiment

## Source baseline and preregistration
- Main base: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- Acquisition proposal: PR #428, `e676c961d674ffd32d254bb96f738ae7242e211f`.
- Experiment branch: `research/2026-11-11-chennai-batch-integration`.
- Implementation commit: `ff501a56c9a888d9bc6dbfc10febfaf5ffc3d42c`.
- Sample ID: `web:wta:1148:2026:LS001`, Linette/Tjen Chennai final.
- Null: invoking the real batch settlement function on the proposed PR #428 input fails a gate or modifies official scorecard/manifest.
- Success: exactly one eligible non-production settlement, correct winner, 64-character provenance hashes, scorecard/manifest byte-preserved. Failure: any exception, denominator mismatch, or mutation.
- Baseline: previous 12 read-only identity checks (PR #446), which did not execute settlement. Comparison: actual `settle_web_shadow_result_batch` execution in pytest on the acquisition proposal checkout.
- Command: `PYTHONPATH=src pytest -q tests/test_chennai_acquisition_batch_integration.py`; broader CI pytest and Ruff must also pass.
- The test uses temporary output only; no production scorecard changes or settlement approval.

## Executed evidence and limitations
- Fetched actual source `scripts/settle_web_shadow_result_batch.py` (blob `fe3da0495e67bcf3e9e6013d15307697df4af4d6`) and `scripts/settle_web_shadow_prediction.py` (blob `f4e9aeb61556d59423c1e25450338631fd28f1b5`).
- Fetched actual PR #428 manifest (blob `3bd8dde18bc70f6c411bfc9a56151577b07340e7`) and proposed result (blob `8693ebd69e6acb4158721251809fedb046abba18`).
- Confirmed PR #446 exact-head CI success run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43070318981 (does not prove PR #428 settlement).
- Local `git ls-remote https://github.com/AidanDCM/Tennis-Genome-.git HEAD` failed with `Could not resolve host: github.com`; **no local pytest executed**.
- Created isolated branch, committed a real-function integration regression, and opened draft PR #447 https://github.com/AidanDCM/Tennis-Genome-/pull/447.
- Immediately after PR creation, exact-head workflow query returned **zero runs**. Therefore settlement integration hypothesis **not yet verified**. Do not claim the test passed.
- PR #447 contains the unmerged acquisition proposal files because its branch is based on PR #428. Never merge without separate human review.
- Main non-production WTA Web Shadow: 85 eligible, 46 correct (54.12%), Brier 0.251461, log loss 0.696908; 16 pending. Qualified production-forward N not refreshed; no new performance claim.

## Independent research / contrary evidence
- Bunker et al., *A comparative evaluation of Elo ratings- and machine learning-based methods for tennis match result prediction*, first online 2023-11-10, https://doi.org/10.1177/17543371231212235. Fourteen annual chronological ATP test periods (2007–2020), unlike WTA Web Shadow; strong ML results depend substantially on a prohibited input family, so those models cannot be transferred unchanged. Publisher reuse restrictions apply. Transferable: chronological evaluation and Elo as simple baseline, not its headline accuracy.
- Buhamra and Groll (2025 preprint), *Statistical enhanced learning for modeling and prediction tennis matches at Grand Slam tournaments*, https://arxiv.org/abs/2502.01613. Uses external testing, rolling/expanding windows and Brier/likelihood; ATP Grand Slam population, uncertain code/license reproducibility. Transferable: time-aware ablation of Elo and age features only if historical pre-start snapshots are available.
- Contrary hypothesis: simpler overall Elo may match or exceed complex models when prospective labels are clean; test against champion without repeatedly tuning the same 78 historical paired observations.

## Prioritized next executable queue
1. Inspect exact-head PR #447 GitHub CI; if failed, inspect traceback and repair the isolated regression, rerun. Capture exact run ID, SHA, pytest count and negative results.
2. Independently inspect the produced settlement artifact hashes and official-source identity gates before any PR #428 human review; do not automatically publish.
3. Restore acquisition for 13 unresolved records, retain 2 identity conflicts excluded, and refresh qualified production-forward scorecard.
4. Pre-register simple overall Elo versus immutable champion on future locked WTA matches, paired Brier/log loss with uncertainty, chronological cohorts and untouched holdout. No model promotion without evidence.

# CI test-count reconciliation — 2026-11-13

**Evidence tier:** operational CI/test coverage; not model performance. **No production changes.**

## Prespecified operational hypothesis
The 14-test difference between successful PR #490 and #492 CI artifacts is explained by the newly added WTA pending-diagnostic test module on #490, absent from #492's independently branched checkout. Reject if module's collected count differs from 14, or if the file is present in both checkouts. Baseline: PR #492 1310 passed; comparison: PR #490 1324 passed. No prediction outcomes used.

## Executed evidence and reproducibility
- PR #490 [run 43463132892](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892): 1324 passed, 2 warnings (previously retrieved artifact 14055789921), checkout merge SHA `6b5d379970f83005c8c34e47538f558afe682d6f`.
- PR #492 [run 43475183219](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43475183219): 1310 passed, 2 warnings (previously retrieved artifact 14063455755), checkout merge SHA `bff0e11`.
- Fetched `tests/test_diagnose_wta_pending_matches.py` at PR #490 merge commit: blob `f2a0e1c6a1d8b20fa4bdf801ec1b979ea2ac44cb`, [source](https://github.com/AidanDCM/Tennis-Genome-/blob/6b5d379/tests/test_diagnose_wta_pending_matches.py). Fetched same path at PR #492 merge commit: GitHub 404 (absent).
- Executed deterministic JS source inspection against fetched file: 11 `test_*` function definitions, one `@pytest.mark.parametrize("token", ["+1024", "1025", "1024.0", "1e3"])` with four instances; expected collection **10 + 4 = 14**. Numerical assertion **1324 - 1310 = 14** passed. This accounts exactly for the difference under the standard pytest collection rules; it does not constitute a full `pytest --collect-only` comparison.
- Reproduction on both historical checkouts: `git checkout 6b5d379 && python -m pytest --collect-only -q tests/test_diagnose_wta_pending_matches.py` (expected 14); `git checkout bff0e11 && test ! -e tests/test_diagnose_wta_pending_matches.py`. Compare full manifests using `python -m pytest --collect-only -q > collected.txt` at each ref, after installing `requirements/ci.lock`.
- GitHub compare API showed the two merge refs **diverged**, sharing base `40bb697ec786527b7ed1a4c67d6d0a92aea17782`; its per-file list reflects the head side only, so do not mistake it for a symmetric file diff.
- Exact count coincidence plus missing file strongly explains the difference; a full collection diff is still needed to exclude offsetting unrelated additions/deletions. No CI workflow rerun was performed in this iteration.

## External methods and limitations
- [pytest parametrization documentation](https://pytest.org/en/latest/how-to/parametrize.html), current official documentation: a parametrized function generates one test per argument set. [pytest collection examples](https://pytest.org/en/latest/example/parametrize.html) show `--collect-only` for independent confirmation. Official docs, no third-party code imported or license transfer.
- [SMBench (2026)](https://doi.org/10.1016/j.is.2026.102711), entity-resolution candidate filtering versus verification: relevant contrary evidence that a candidate match is not a verified settlement; published benchmark population differs from tennis and no performance claims transfer. Research reference only, no code imported.

## Independent evidence and negative controls
Main non-production WTA Web Shadow `web-shadow/scorecard.json` blob `c9636ac9d86c256ccf241e652b9456034c451fc3`: 47/86 correct (54.65%), Brier 0.2513224181, log loss 0.6966212009; 15 pending. Paired Elo comparison N=79, Genome Brier 0.2522696015 versus Elo 0.2578582137; not prospective production evidence. PR #490 diagnostic records 12 round discrepancies, one missing pair, two exact-ID player conflicts. Main CI workflow `.github/workflows/ci.yml` blob `519d3534215ca315faed2248dcafa3d1d9ff71fd` uses pull_request merge checkout and redirects test stdout to artifacts. Frozen production bundle digest recorded as `7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1`; cumulative qualified forward N not freshly validated. **No new qualified observations, settlements, model lift, or promotion.**

## Prioritized next executable queue
1. Fetch active acquisition workflow and latest capture run, inspect failure/zero-selection diagnostics; independently verify champion freeze and qualified forward sample counts.
2. Run exact checkout full `pytest --collect-only` manifest comparison to rule out offsetting test differences.
3. Validate pre-start identities and round provenance of 15 pending shadow records with independent official source; do not backfill or weaken strict gates.
4. After new qualified prospective locks, preregister one fixed shrinkage challenger and paired champion comparison with Brier, log loss, confidence intervals and untouched final holdout.

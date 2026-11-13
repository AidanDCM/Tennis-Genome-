# CI diagnostic artifact verification — 2026-11-13

**Tier:** operational test-provenance evidence, not model performance. **Scope:** read-only inspection of retained CI artifacts; frozen champion, predictions, results, eligibility gates, and production remain unchanged.

## Preregistered check
Hypothesis: raw CI logs' success statuses are sufficient to establish exact test counts. Alternative: redirected `pytest > pytest.txt 2>&1` and `ruff check . --output-format=concise > ruff.txt 2>&1` require artifact inspection. Success criterion: independently retrieve both ZIP artifacts, read both files and report exact counts/warnings without conflating merge refs with branch heads. Compare PR #490 and PR #492 only for operational CI provenance, not as paired predictive experiments.

## Executed evidence
- [PR #490 run 43463132892](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892), artifact [14055789921](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892/artifacts/14055789921), SHA256 manifest digest `03c989373807feea896f31d7a0177b5c694fb01bdf3d2f0877f3b4bfe3c7885f`. Downloaded ZIP through GitHub connector; Python `zipfile.ZipFile(...).read('pytest.txt')` yielded **1324 passed, 2 warnings in 29.86s**; `ruff.txt`: **All checks passed!** Checkout synthetic PR merge HEAD `6b5d379`; PR head `007f7bde1f994df5427cdff88188ea3a8bffcf0f`.
- [PR #492 run 43475183219](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43475183219), artifact [14063455755](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43475183219/artifacts/14063455755). Downloaded ZIP and inspected `pytest.txt`: **1310 passed, 2 warnings in 20.54s**; `ruff.txt`: **All checks passed!** Checkout synthetic PR merge HEAD `bff0e11`; PR head `3745a6c6fb51ae57c4ea0b57951f9b2cb79da7e5`.
- Both warnings: Python invalid escape sequence `\\+` in `tests/test_full_slate_cutover.py:201` and `tests/test_pattern_confirm_live.py:674`. Warnings did not fail CI. The **14-test difference** is not evidence of missing or added coverage without comparing checkout trees/test collection; no causal explanation asserted.
- Reproduction: GitHub `fetch_workflow_run_artifacts` then `download_workflow_artifact` using artifact IDs above; `python -c "import zipfile; z=zipfile.ZipFile('artifact.zip'); print(z.read('pytest.txt').decode()[-1500:]); print(z.read('ruff.txt').decode())"`. Verified actual artifact contents, not a fresh test-suite execution. GitHub CI itself executed tests at the recorded merge commits.

## Research and contrary evidence
- Loveday, Taggart, Khanarmuei (2024), [User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts](https://doi.org/10.1175/WAF-D-23-0201.1), peer-reviewed weather-forecast verification: proper scoring and threshold diagnostics; tennis adaptation requires binary match labels, pre-start locks and independent future evaluation. External weather results are not tennis performance estimates. Default publisher reuse terms; no code imported.
- Kleen (2024), [Scaling and measurement error sensitivity of scoring rules](https://doi.org/10.1002/jae.3056), open-access journal study: outcome measurement errors can change forecast rankings, especially log score; reinforces identity adjudication before score comparisons. Data are economics/finance, not tennis; no transferred effect size or code.
- [GitHub Actions checkout documentation](https://github.com/actions/checkout): default pull-request merge ref is distinct from literal PR head; record both in test evidence.

## Production evidence and negative result
Main `web-shadow/scorecard.json` blob `c9636ac9d86c256ccf241e652b9456034c451fc3`: **non-production** WTA 47/86 (54.65%), Brier 0.2513224181, log loss 0.6966212009, 15 pending; paired Elo cohort N=79, Genome Brier 0.2522696015 vs Elo 0.2578582137. Not production-qualified. Main champion and cumulative verified forward sample not independently rechecked in this run; **no new independent model-performance evidence**. PR #490 diagnostic: 12 round mismatches, one absent pair, two identity conflicts; no retrospective settlement.

## Next executable queue
1. Compare PR #490 and #492 exact test collection manifests/tree diffs to explain 14-test discrepancy, without treating difference as regression.
2. Audit main's active capture workflows, frozen champion SHA, qualified prospective sample denominator, and current acquisition logs.
3. Independently verify 15 unresolved identities against independent contemporaneous sources; do not weaken matching or backfill.
4. Once genuinely new pre-start observations are locked, preregister one fixed shrinkage challenger versus champion and 0.5, paired chronological Brier/log loss and uncertainty intervals, with untouched final holdout.

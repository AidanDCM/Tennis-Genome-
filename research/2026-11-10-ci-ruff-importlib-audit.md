# 2026-11-10: exact-head CI lint diagnosis and safe regression-test import repair

## Evidence and status
- Research PR: https://github.com/AidanDCM/Tennis-Genome-/pull/429 (draft, never promote automatically); base main at 8af76720a6291b166263fa1cd8191504f84ed6b6, inspected head 88e9008a2f106ca782c7461b3d19e140d627ee4e.
- Result capture PR: https://github.com/AidanDCM/Tennis-Genome-/pull/428 (open, no automatic merge); its snapshot reports 16 pending inspected, 1 finished captured, 13 unmatched, 2 player identity conflicts.
- Inspected actual exact-head CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42770487660, job 129676864971: Ruff exit 1, `tests/test_research_calibration_signflip_real.py:7:1 I001`; pytest **1330 passed, 2 warnings**. Workflow's step summaries misleadingly show 'success' for command wrappers; 'Enforce checks' fails and logs expose the underlying exit code.
- Test source blob before repair df3c1e5efa8918d26ec07756ecccb8d78c507823; `pyproject.toml` blob 90e244a5a7805748eb5611cea3c415f42cb55cbd. CI lock pins Ruff 0.16.7.
- Narrow fix commit **5658c2ffed4769c1087f66b6363dee3a1b655b2e**: avoid Ruff's ambiguous classification of `scripts` namespace import in test module by resolving it with `importlib.import_module` inside the fixture. No prediction/settlement/champion edits. Expected behavior unchanged, but **new commit has no confirmed CI** at time of check. Do not claim green.
- Local attempts: `python -m ruff --version` returned No module named ruff; `git ls-remote https://github.com/AidanDCM/Tennis-Genome-.git HEAD` failed with Could not resolve host: github.com. No local repo suite was executed.

## Hypothesis, controls, and gates
Hypothesis (engineering): removing direct import classification ambiguity eliminates I001 without changing the 7 historical regression tests. Baseline: preceding exact-head 1330 passing pytest, Ruff I001. Success only if **same new SHA** has Ruff clean and 1330+ passing tests, no reduced coverage. Failure if I001 persists or test count/behavior changes. Do not merge on incomplete CI.
Historical calibration research control remains 55 non-production WTA paper matches / 15 UTC dates, fixed slope 0.5 versus baseline slope 1.0; earlier Brier improvement +0.01089 and exploratory sign-flip fraction 0.2145 are **not** independent evidence. The non-production WTA scorecard was read from main this run but the complete qualified forward settlement aggregate was not refreshed, so no current prospective N is asserted.

## External research (rotated theme: forecast scoring / adverse evidence)
- Waghmare & Ziegel, *Proper Scoring Rules for Estimation and Forecast Evaluation*, Annual Review of Statistics and Its Application, advance 2025 / volume 2026, https://doi.org/10.1146/annurev-statistics-042424-050626 (CC BY 4.0). Proper scores support Brier and log-loss paired evaluation, but do not by themselves solve dependence or selection bias.
- Pic et al., *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, published 2025, https://doi.org/10.5194/ascmo-11-23-2025 (CC BY 4.0). Complementary scoring rules can expose failures hidden by one aggregate metric; multivariate specifics not directly transferable to binary tennis.
- Marcotte et al., *Regions of Reliability in the Evaluation of Multivariate Probabilistic Forecasts*, 2023 preprint https://arxiv.org/abs/2304.09836. Finite-sample power can be weak even with proper scores. Caution: multivariate time-series synthetic/energy-domain results not directly comparable to tennis.

## Reproduction
```bash
python -m pip install -r requirements/ci.lock
python -m pip install -e .
ruff check . --output-format=concise
pytest -q tests/test_research_calibration_signflip_real.py
pytest
python scripts/research_calibration_signflip_real.py --repo-root .
```

## Prioritized queue
1. Verify CI at 5658c2ffed4769c1087f66b6363dee3a1b655b2e; inspect raw Ruff output; if failure, obtain exact `ruff check --diff` on the pinned version and fix safely.
2. Inspect official WTA result capture identities in PR #428 against source IDs/times; reject conflicts, do not backfill or weaken provenance; verify forward settlement aggregate and workflow freshness.
3. Prespecified leave-one-date-cluster-out fixed-half versus original on 55 historical IDs, report all 15 deltas (Brier/log-loss) and sensitivity, not confirmatory claims; freeze prospective comparison before collecting new labels.

# 2026-11-11 — Chennai integration CI verification

## Experiment and baseline
- Immutable main base recorded by PR #447: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- Proposed acquisition PR #428; integration PR #447 head `bff7013a3da3ecd133bac0310f7abd65066e9897`.
- Sample ID: `web:wta:1148:2026:LS001` (Chennai Linette–Tjen).
- Preregistered hypothesis (from PR #447): invoking actual `settle_web_shadow_result_batch` on PR #428's proposal produces one eligible non-production settlement without mutating original manifest or scorecard.
- Baseline: 12 read-only identity checks in PR #446. Challenger: actual settlement function in isolated temporary-output pytest.
- Success: exact assertions in `tests/test_chennai_acquisition_batch_integration.py` and Ruff/pytest green; failure: any failed assertion, exception, or mutation.
- Reproduce: checkout PR #447 head; `PYTHONPATH=src pytest -q tests/test_chennai_acquisition_batch_integration.py`; `ruff check .`; `pytest`.

## Actual observed execution
- GitHub Actions run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43080766329
- Run's test job ID `130732398768` completed **success**; checkout, Python setup, dependency install, Ruff, pytest, and diagnostics upload each completed successfully.
- Retrieved actual job logs. Ruff and pytest output were redirected to `ruff.txt` and `pytest.txt`; log shows successful execution and uploaded diagnostics artifact ID `13883129305`, SHA-256 `799c485b8c505e7b240ef32df95ed58b67c8c72790d620fe60e8abbdcb8f45c2`.
- The job log does **not** print pytest test count or the settlement output payload; do not claim independently inspected artifact contents.
- The passing integration test supports the tested function contract on this branch only; it does not independently validate provider identity, provenance authenticity, or production publication.
- No production settlement, champion, or frozen prediction changed in this audit.

## Evidence tier and negative findings
- Main WTA Web Shadow is explicitly non-production: 88 settled records, 85 eligible scored, 46 correct (54.12%), Brier 0.2514610585, log loss 0.6969082733, 16 pending.
- Paired historical Elo comparison: 78 shared, Genome 41 correct versus Elo 42; Genome Brier 0.2524328274 versus Elo 0.2597451904. Not prospective superiority.
- Production qualified forward N was not refreshed. Acquisition PR #428 remains unmerged; 13 unresolved matches and 2 identity conflicts remain excluded.
- No additional predictive-model ablation was executed this iteration; this is an infrastructure trust-gate test.

## Research comparison and transfer
- Brenowitz et al. (2025), *A Practical Probabilistic Benchmark for AI Weather Models*, https://doi.org/10.1029/2024GL113656. Open-access paper, parameter-free probabilistic benchmarking, reports deterministic ranking can diverge from probabilistic quality. Weather domain; no direct tennis transfer, license for code not verified. Transfer: fixed, paired probability-score comparisons.
- Loveday, Taggart & Khanarmuei (2024), *A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts*, https://doi.org/10.1175/WAF-D-23-0201.1. Published journal article, threshold diagnostics plus proper scoring; not evidence of tennis accuracy, code license not verified. Transfer: report probability scores rather than accuracy alone.
- Contrary hypothesis: simple overall Elo may generalize as well as or better than a complex champion; only new chronologically locked paired samples can adjudicate.

## Prioritized executable queue
1. Retrieve CI diagnostics artifact and independently inspect the settlement summary, hash bindings, and pytest count, without publishing anything.
2. Review PR #428 source and provenance, including all exclusions, before any human settlement approval; do not merge this audit into acquisition.
3. Restore safe WTA acquisition for unresolved predictions, retaining identity-conflicted cases excluded; refresh qualified forward evidence.
4. Pre-register paired frozen-champion vs simple Elo experiment on new chronologically locked WTA matches, Brier/log loss, calibration, confidence intervals and time/surface cohorts; no holdout tuning or automatic promotion.

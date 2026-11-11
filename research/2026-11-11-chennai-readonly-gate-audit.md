# 2026-11-11 — Chennai acquisition pre-settlement gate audit (read-only)

## Baseline and question
Main commit: `8af76720a6291b166263fa1cd8191504f84ed6b6`. Main scorecard blob: `60082a6292087e2b6e902faca79f2f4c847d8fdb`. Proposed acquisition: PR #428 at `e676c961d674ffd32d254bb96f738ae7242e211f`. Sample: `web:wta:1148:2026:LS001` (Chennai final, Magda Linette / Janice Tjen).

Preregistered hypothesis: the proposed Chennai result matches a currently pending frozen prediction and the proposed single-item manifest, with valid non-production isolation and chronological result observation. Null: at least one gate fails. Acceptance: all twelve read-only assertions true. This is **not** the full settlement dry-run, source re-fetch, or settlement approval.

## Executed read-only experiment
Fetched four actual repository JSON files using connected GitHub `fetch_file`, parsed and compared fields programmatically in a JavaScript evaluation. Files and blob SHAs:
- `web-shadow/scorecard.json` (main): `60082a6292087e2b6e902faca79f2f4c847d8fdb`
- `web-shadow/active-results.json` (refs/pull/428/head): `3bd8dde18bc70f6c411bfc9a56151577b07340e7`
- `web-shadow/results/2026-11-09-chennai-2026-f-ls001-janice-tjen-magda-linette-42775ef387.json` (PR #428): `8693ebd69e6acb4158721251809fedb046abba18`
- `web-shadow/slates/2026-11-07-run-42418376306/predictions/chennai-2026-f-ls001-janice-tjen-magda-linette.json` (main): `799ce2152166bf238adca39271de8c102519348c`

Checks **12/12 PASS**: manifest has one result; manifest points to proposed result; prediction currently PENDING; SHA equals scorecard SHA; match ID equals scorecard ID; slate ID matches; prediction fixture match ID matches; prediction production_eligible=false; result production_eligible=false; result COMPLETED; winner belongs to frozen pair; result_observed_at > scheduled_start. Original scheduled start `2026-11-08T18:30:00+05:30`, observed `2026-11-09T08:39:51+00:00`. Frozen probability for Magda Linette `0.510573822024917`.

The real workflow source `.github/workflows/wta_web_shadow_settlement_batch.yml` (blob `81eea3a94f2b05b35f4209f658e9977221de3bcf`) calls `python -m scripts.settle_web_shadow_result_batch --manifest ... --scorecard ... --output-root ...`. The settlement script (blob `fe3da0495e67bcf3e9e6013d15307697df4af4d6`) has additional checks not executed here, including `settle_from_result_file` validation. Local `git ls-remote` attempt failed `Could not resolve host: github.com`, so full local dry-run did not run. **Do not mistake source contract inspection for successful integration execution.**

PR #445 exact-head GitHub workflow run #43061456725 completed with conclusion `success`; this validates that PR's CI, not PR #428 settlement.

## Evaluation and negative results
Main non-production WTA Web Shadow: 88 settled records, 85 evaluation eligible, 46 correct, accuracy 46/85=54.12%, Brier 0.251461, log loss 0.696908, 16 pending. No new production-qualified forward sample was established. This read-only audit does not change any denominator or score. PR #428 reports 13 unresolved predictions and 2 identity conflicts held out; those remain excluded. PR #428 is open and requires human review. No production champion, prediction, settlement, or scorecard changed.

## External research and contrary considerations
- Loveday, Taggart & Khanarmuei (2024), *A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts*, Weather and Forecasting, DOI https://doi.org/10.1175/WAF-D-23-0201.1. Published 2024-08-08. Meteorological binary forecasts and proper scoring comparisons; relevant to eventual threshold-sensitive diagnostics, not directly comparable tennis accuracy. Journal reuse terms apply.
- Einbinder et al. (2024), *Label Noise Robustness of Conformal Prediction*, JMLR 25(328), https://jmlr.org/papers/v25/23-1549.html. Theory and experiments on noisy-label conformal coverage; not evidence that Tennis Genome has known noise rates or that conformal adjustment improves winner probability.
- Pacchiardi et al. (2024), *Probabilistic Forecasting with Generative Networks via Scoring Rule Minimization*, JMLR 25(45), https://jmlr.org/papers/v25/23-0038.html (CC BY 4.0 available). Sequential weather/dynamical benchmark, high complexity; not a justified next model upgrade with current evidence bottleneck.

## Next executable queue
1. Run actual `PYTHONPATH=src python -m scripts.settle_web_shadow_result_batch --manifest web-shadow/active-results.json --scorecard web-shadow/scorecard.json --output-root /tmp/chennai-settlement-audit` in an isolated checkout of PR #428 (or a safe exact-head CI job), inspect produced summary and record SHA, never publish automatically.
2. Verify workflow source timestamps and official WTA upstream identity; resolve 13 unmatched and 2 conflicts without weakening gates.
3. Refresh independent forward-validation aggregate and report qualified N; only then preregister a chronological paired Elo-vs-champion probability-score test with untouched final holdout.

# Live WTA acquisition zero-selection evidence — 2026-11-13 22:41 UTC

## Preregistered operational hypothesis
H0: Latest successful scheduled WTA result/intake jobs produced a proposal or selected eligible matches. Reject if their actual logs show zero results or no eligible unseen intake, despite successful jobs. Compare both independent workflows to source-level guard baseline; no model-performance inference.

## Pinned source and sample
Main SHA: `40bb697ec786527b7ed1a4c67d6d0a92aea17782` (2026-11-12 17:33 UTC).
Result job: [run 43472171946](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43472171946), job 132046596768, 2026-11-13 17:22 UTC.
Intake job: [run 43495625075](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43495625075), job 132127831695, 2026-11-13 19:48 UTC.
Read GitHub Actions job step statuses and actual decoded logs using `fetch_workflow_run_jobs` and `fetch_workflow_job_logs`; reproducible REST reads:
```sh
gh api repos/AidanDCM/Tennis-Genome-/actions/runs/43472171946/jobs
gh api repos/AidanDCM/Tennis-Genome-/actions/jobs/132046596768/logs > result-job.log
gh api repos/AidanDCM/Tennis-Genome-/actions/runs/43495625075/jobs
gh api repos/AidanDCM/Tennis-Genome-/actions/jobs/132127831695/logs > intake-job.log
grep -E 'result_count|pending_prediction_count|unresolved_prediction_count|identity_conflict_count|No eligible unseen matches|source_count' {result,intake}-job.log
```

## Observed outcomes (not inferred from green CI)
Result source fetch: index_count=2, source_count=10. Compiler JSON: `{"identity_conflict_count":2,"pending_prediction_count":15,"result_count":0,"snapshot_id":"wta-results-20261113t172239z","unfinished_prediction_count":0,"unresolved_prediction_count":13}`. Dry-run, proposal mutation verification, commit and PR steps skipped. Gate output observed `GATE_BLOCKED: false`. Thus **allowed but zero selected**; not an existing-proposal gate block.

Intake source fetch: index_count=2, source_count=4; log: `No eligible unseen matches in the frozen intake window.` Selection/binding, verification, commit, PR, exact-head CI and merged-slate steps skipped. Job conclusion success. Thus **source retrieval succeeded but intake selection empty**.

Negative controls: a green job does NOT prove a new proposal or qualified prospective match; neither zero count establishes an outage. The two jobs concern different selection populations and source snapshots, so their source_count values must not be compared as if identical. No pending prediction was settled. This run did not download retained acquisition artifacts or independently adjudicate official IDs.

## Current evidence tier
Main non-production `web-shadow/scorecard.json`: 47/86 winner correct (54.65%), Brier 0.2513224181, log loss 0.6966212009; 15 pending, `production_eligible=false`; separate paired Elo cohort N=79. Production frozen champion and cumulative qualified forward N not re-established from raw receipts here. Never count shadow as production evidence.

## Methodological research and contrary evidence
- Loveday, Taggart & Khanarmuei (2024), *Weather and Forecasting*, https://doi.org/10.1175/WAF-D-23-0201.1 — proper scores and threshold-specific evaluation, demonstrated on weather and synthetic binary data; no tennis transfer claim; journal reuse restrictions apply.
- Dominitz & Manski (2024), NBER working paper https://www.nber.org/papers/w32269 — out-of-sample evaluation must confront changes in target populations, not just random folds; working-paper status, not a validated tennis implementation.
- Kleen (2024), https://doi.org/10.1002/jae.3056 — measurement error can change probabilistic scoring comparisons; open access, but economic continuous-outcome examples, not tennis. This is contrary evidence against treating identity-uncertain labels as valid calibration targets.

## Next executable queue
1. Download and parse retained result/intake acquisition artifacts for these exact run IDs. Attribute 13 unresolved to explicit reason codes and verify two identity conflicts against independently retained official source IDs. Do not alter history or gates.
2. Audit frozen-window intake candidate counts by rejection reason, source coverage and pre-start timestamps, including a controlled replay of the same pinned sources.
3. Reconcile immutable champion and forward qualified N from signed/hashed receipts and latest forward aggregate artifact; separate all shadow evidence.
4. Only after new qualified observations, preregister one shrinkage challenger and compare paired prospective Brier/log loss with unchanged champion and fixed-0.5 negative control.

No model promotion, settlement, gate weakening, gambling data or production changes.

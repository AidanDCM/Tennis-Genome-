# CI merge-checkout provenance audit — 2026-11-13

**Tier:** operational verification, no production performance claim. **Scope:** CI provenance and independent evaluation integrity; no model, settlement, prediction or trust-gate edits.

## Prespecified falsifiable check
Hypothesis: successful PR CI jobs #43463132892 (PR #490) and #43475183219 (PR #492) check out the literal branch head. Control: they instead check out GitHub-generated PR merge refs. Pass if checkout lines explicitly show the head SHA; reject if merge ref and synthetic merge SHA appear. Read the workflow at main `.github/workflows/ci.yml`, blob `519d3534215ca315faed2248dcafa3d1d9ff71fd`.

## Executed source inspection and results
Connector calls: `fetch_workflow_run_jobs(repo_full_name="AidanDCM/Tennis-Genome-",run_id=43463132892)`; `fetch_workflow_job_logs(...,job_id=132015061757)`; analogous run `43475183219`, job `132057088107`. Filter raw job logs for `Checking out the ref`, `git checkout`, `HEAD is now`, `ruff check`, and `pytest >`.

- [PR #490 run 43463132892](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892): checkout `refs/remotes/pull/490/merge`, HEAD `6b5d379`, synthetic merge of PR head `007f7bde1f994df5427cdff88188ea3a8bffcf0f` into main `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Job test concluded success, Ruff and Pytest steps success, enforcement step skipped as designed.
- [PR #492 run 43475183219](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43475183219): checkout `refs/remotes/pull/492/merge`, HEAD `bff0e11`, synthetic merge of PR head `3745a6c6fb51ae57c4ea0b57951f9b2cb79da7e5` into same main. Job success, Ruff/Pytest steps success, enforcement skipped.
- **Negative result:** Neither run checked out literal PR head; do not describe either as exact-head CI. They *do* test proposed changes integrated with then-current main. Workflow `pull_request` with default `actions/checkout@v4` explains merge-ref checkout. No claim that tests were run locally.
- Diagnostics artifacts: [#490](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892/artifacts/14055789921) and [#492](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43475183219/artifacts/14063455755). Logs redirect test stdout to artifact files, so job logs alone do not disclose pytest count.

## Shadow and evidence gates
Main `web-shadow/scorecard.json` blob `c9636ac9d86c256ccf241e652b9456034c451fc3`: non-production WTA shadow scored 47/86, Brier 0.2513224181, log loss 0.6966212009, pending 15; paired Elo N=79, genome Brier 0.2522696015 vs Elo 0.2578582137, genome log loss 0.6983470279 vs Elo 0.7186905603. These are distinct denominators and observational cohorts; none independently qualifies as production forward validation. No new settlement adjudicated. PR #490 reports 12 round discrepancies, one missing pair, two exact-ID conflicts. Champion and qualified forward sample not reverified in this operational audit.

## Research and contrary evidence
- Bröcker (2008), [Some Remarks on the Reliability of Categorical Probability Forecasts](https://doi.org/10.1175/2008MWR2329.1), peer-reviewed: estimated calibration functions can be noisy and recalibration can degrade scores; supports refusing to promote bucket-based fixes without forward tests. No code or data imported.
- Dimitriadis, Gneiting and Jordan (2020), [CORP](https://arxiv.org/abs/2008.03033), preprint/open methodology: reproducible isotonic reliability diagrams are a future diagnostic candidate, but fitting to the 86 scored observations would reuse evaluation data. Software/license not verified, no code imported.
- Gneiting, Balabdaoui and Raftery (2007), [Probabilistic forecasts, calibration and sharpness](https://doi.org/10.1111/j.1467-9868.2007.00587.x): distinguish sharpness from calibration; proper scoring and independent chronological evaluation required. Not tennis-specific, so no transferred performance claim.

## Prioritized executable queue
1. Fetch CI diagnostic artifact and verify actual pytest count and Ruff stdout; pin checkout and main/PR SHAs in future ledger entries.
2. Independently resolve the 15 pending shadow identities against anchored original source evidence, without retroactive settlements.
3. Audit live pre-start capture and qualified production-forward denominator, then preregister one fixed simple shrinkage challenger for future paired, locked predictions; report paired proper scores, confidence intervals, coverage and drift. Keep champion and untouched holdout immutable.

**Reproduction:** GitHub connector `fetch_workflow_run_jobs` and `fetch_workflow_job_logs` with IDs above; grep for checkout and test commands. No numerical model fitting occurred in this iteration.

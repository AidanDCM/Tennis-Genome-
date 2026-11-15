# WTA result identity regression — 2026-11-13 UTC

## Source and baseline
Main commit: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`.
Source: [WTA compiler](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/scripts/web_shadow_wta_result_core.py).
Previous source audit: [PR #478](https://github.com/AidanDCM/Tennis-Genome-/pull/478), 12/13 legacy pending pairs with unique source rows but differing round interpretation; one absent. These are **diagnostic candidates**, not settlement approvals.
Frozen champion, predictions, results, provenance, and trust gates unchanged.

## Falsifiable hypothesis and comparisons
H0 operational expectation: current legacy round-name/round-ID joins and exact official MatchID joins are distinguishable in a synthetic regression suite; no ambiguous or conflicting identity may pass silently.
Prespecified success: all nine cases pass, including three numeric-round cases, two textual-round cases, exact ID missing, wrong player, duplicate legacy identity, wrong event.
Failure: any wrong-player, duplicate, missing MatchID, or wrong-event case produces a settlement match; or a previously documented route behaves differently. This is **not** a model-quality experiment and cannot establish predictive lift.

## Code and reproduction
Test file: `tests/test_wta_round_identity_diagnostic.py`.
Proposed test commit: `ad39902b8b6a6b5d2fa9874f20f2642a38fea7bf`.
Run from repository root: `python -m unittest tests.test_wta_round_identity_diagnostic -v` (or `python -m pytest -q tests/test_wta_round_identity_diagnostic.py`).
No settlement writes, no prediction edits, no data mining or model promotion.

## Observed execution and negative evidence
- A local copy of the test was generated and `python -m py_compile` succeeded.
- `python -m unittest discover -s /mnt/data/tennis_audit -v` **failed before collecting cases** with `ModuleNotFoundError: No module named 'scripts'`. The execution container could not resolve `github.com` during `git ls-remote`, so the repository package was unavailable locally.
- Connected GitHub fetched the real compiler and created the test commit and [draft PR #479](https://github.com/AidanDCM/Tennis-Genome-/pull/479).
- Exact-head workflow query for `ad39902b8b6a6b5d2fa9874f20f2642a38fea7bf` returned **zero runs**. Thus **0/9 runtime cases independently verified**, and no CI pass is claimed.
- No historical settlements or forecast metrics were recalculated this run.

## Research (read-only)
- Gupta et al. (2024), [Manual Evaluation of Record Linkage Algorithm Performance in Four Real-World Datasets](https://pmc.ncbi.nlm.nih.gov/articles/PMC11290950/): independent adjudication can change linkage-quality estimates; clinical datasets, not tennis; published 2024; no implementation imported; publisher rights not independently cleared.
- Papadakis et al. (2024), [A Critical Re-evaluation of Record Linkage Benchmarks](https://doi.org/10.1109/ICDE60146.2024.00265): easy linkage benchmarks may overstate generality; 13 benchmark datasets, not time-ordered tennis fixtures; IEEE publication, no code imported or license asserted.
- Binette et al. (2024), [How to Evaluate Entity Resolution Systems](https://arxiv.org/abs/2404.05622): entity-centric labeling suggests a human-adjudicated positive/negative identity fixture set; no code imported; implementation license unverified.
These are methodological analogies, not comparable win-rate claims.

## Priority queue
1. Run nine tests on actual exact PR head; inspect logs, fix only test-fixture mistakes safely.
2. Verify immutable champion SHA, production-forward qualified N, current scorecard, active workflow state and pre-start evidence on main; do not infer them from this suite.
3. Adjudicate the 12 round-discrepant source candidates with independently verified tournament, schedule and pre-start provenance; keep unresolved pending.
4. Add read-only structured mismatch reason reporting with negative controls, no settlement eligibility change.
5. After new prospective qualified matches, preregister paired chronological Brier/log-loss evaluation versus frozen champion, Elo and fixed-0.5 with untouched holdout.

## 2026-11-13 follow-up: exact-head CI diagnosis and safe correction
- Original PR head: `7b44c63f6773243a134af37afc8a3c524944f01a`.
- [Exact-head CI run #43338930393](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43338930393) finished **failure**. Job #131602087105 logs show **1319 pytest passed, 2 warnings in 23.10 s**, including the nine new cases. Ruff failed with **I001 import ordering** in `tests/test_wta_round_identity_diagnostic.py:2`. The final enforce step failed; never label this run green.
- Safe correction: import-only sorting commit `d0205696d1a9eee191ff0f7046a236a65b17fe50`, no changed test assertions, matching logic, prediction or settlement. Exact-head workflow lookup immediately after commit returned zero runs; new-head green CI **not yet verified**.
- Reproduce: `ruff check tests/test_wta_round_identity_diagnostic.py`; `pytest -q tests/test_wta_round_identity_diagnostic.py`; full `ruff check .` and `pytest` on corrected head. Current container cannot DNS-resolve github.com, so GitHub Actions remains authoritative for repository runtime.
- Adjacent contrary evidence: [Loveday, Taggart & Khanarmuei (2024)](https://doi.org/10.1175/WAF-D-23-0201.1) show threshold-specific diagnostics and proper scoring can reveal different forecast behavior; weather binary outcomes, not tennis, AMS reuse restrictions, no code imported. [Dominitz & Manski (2024)](https://www.nber.org/papers/w32269) argue evaluation must address changing prediction populations; methodological discussion, no tennis sample or comparable headline accuracy, no code imported.
- Next queue: (1) verify corrected-head CI; (2) independently review pre-start provenance for 12 round-discrepant cases; (3) diagnostic-only mismatch categories; (4) new prospective matched predictions and chronological paired scores; (5) reverify champion manifest and forward sample counts.


## 2026-11-13 follow-up: corrected-head failure and second isolation fix
- PR #479 head `805c741a4992ceafb9e31a5d8bb6a799df58d159` ran [CI #43346348325](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43346348325). Actual job #131626530871 output: **1319 passed, 2 warnings in 27.33s**, but Ruff **I001** persisted on line 2; full CI conclusion **failure**. Prior import-order-only correction was insufficient; this is a negative result, not green CI.
- The same run uploaded [diagnostics artifact #14002191023](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43346348325/artifacts/14002191023); job logs explicitly print the Ruff error and pytest summary.
- Two safe test-only commits: `3026cb5070df80929ee39676dbee6720aa79ed83` changes the mixed-case named import to a single module alias, then `f1ab84e00256806f8a75bfa50937b77ec778e287` separates module docstring, standard-library and repository imports with blank lines. No test assertion or settlement code changed. Both corrections require fresh exact-head CI; the initial lookup on the first correction returned no runs.
- Local `pip install ruff==0.16.7` failed because the execution environment cannot resolve the package index, so no local Ruff pass is claimed. Reproduce on GitHub runner: `ruff check . --output-format=concise` and `pytest`. If I001 persists, inspect Ruff's suggested `ruff check tests/test_wta_round_identity_diagnostic.py --fix --diff` and apply only the formatting change.
- New external research: [Pic et al. (2025)](https://doi.org/10.5194/ascmo-11-23-2025) demonstrate complementary proper scores and diagnostic discrimination in wind-speed forecasting, using simulation and real-world data, not tennis; article CC BY 4.0, R implementation linked but its repository license not independently checked. [Allen et al. (2025)](https://doi.org/10.1080/01621459.2025.2506194) discuss tail-calibration pitfalls in precipitation; different outcome/population and no imported code. Neither provides comparable tennis accuracy.
- Priority: (1) inspect exact-head CI on `f1ab84e` and repair any formatting-only issue; (2) independently verify main/champion/qualified forward N; (3) adjudicate 12 identity candidates without settlement writes; (4) add read-only mismatch reason reporting; (5) only then test a preregistered chronological challenger on newly locked qualified samples.

## 2026-11-13 follow-up: exact CI E501 and third minimal fix
- Exact PR head `9dce708da033322f96974ebacde93eddef444ceb`: [CI #43353580672](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43353580672) completed **failure**. Job #131650171371 logged **1319 passed, 2 warnings in 33.98s**; Ruff failed with **E501** at `tests/test_wta_round_identity_diagnostic.py:45:101` (101 > 100 characters). Prior I001 issue is absent, but overall CI was not green.
- Fix commit `cd580f67ad742553930c9f08beb7785280639df8` splits the long exact-textual-round assertion into an intermediate assignment plus the unchanged equality assertion. No compiler, model, prediction, settlement, identity or chronology gate was changed.
- Acceptance: on the exact new head, `ruff check . --output-format=concise` returns zero errors and `pytest` passes all cases. Pending independent CI verification as of ledger write. Commands: `ruff check . --output-format=concise && pytest`.
- Research cross-check: [Waghmare & Ziegel (2026)](https://doi.org/10.1146/annurev-statistics-042424-050626), CC BY 4.0 review of proper scoring rules, supports future paired Brier/log-loss comparisons; [Decker & Tresp (2026)](https://arxiv.org/abs/2611.03592), multi-horizon time-series calibration evaluation, warns that pooled calibration can hide conditional failures. Neither is a tennis experiment, neither implementation was imported, and no external claimed accuracy is comparable. The latter is a recent preprint and its code license is not established.
- Priority queue: (1) verify CI on exact corrected head, fix only observed failures; (2) audit current champion manifest and qualified forward N; (3) independently adjudicate 12 source-row candidates' pre-start evidence and provenance, preserving pending state; (4) implement diagnostic-only mismatch reason reporting with negative controls; (5) prospective chronological paired Brier/log-loss comparison once new qualified observations exist.

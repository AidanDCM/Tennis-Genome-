# Research iteration: CI import-group repair (2026-11-10)

## Verified inputs
- Research branch: research/2026-11-09-calibration-audit; PR #429.
- Prior audit commit: b3e1fb9b254c24f2968523e594f11466adb9f9f4.
- Failed exact-head workflow: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42757731508 (failure).
- Job 129635918799: Ruff I001 at tests/test_research_calibration_signflip_real.py:6:1; pytest **1330 passed, 2 warnings**. This run does NOT pass CI.
- Source blob before repair: 25d89ea10ce8e434e63656088940c6bba5074e61.

## Narrow change
- Commit 50cc6f7b50f5c2e826579d0e7eef75f6e6fbe68a inserts a blank line between third-party pytest and first-party scripts import, leaving test logic unchanged.
- This is a hypothesis about Ruff isort's grouping, **not a verified repair**. No exact-head workflow was returned immediately after commit.
- Reproduce: `ruff check tests/test_research_calibration_signflip_real.py` and `pytest -q tests/test_research_calibration_signflip_real.py`; require full exact-head CI green before closure.

## Research context and negative findings
- Historical calibration comparison: 55 paper predictions across 15 dates; fixed confidence shrinkage yielded mean Brier reduction 0.01089 vs uncalibrated, but earlier sign-flip sensitivity fraction 0.2145; no confirmatory gain or prospective promotion.
- CORP reliability diagrams: Dimitriadis, Gneiting & Jordan (2021), https://doi.org/10.1073/pnas.2016191118. Reproducible calibration diagnostics, but in-sample isotonic fitting is not independent forecast validation. Licensing of external code must be checked before reuse; this iteration copied no external code.
- Data bottleneck: result capture PR #428 retains 2 identity conflicts, 13 unmatched among 16 inspected pending predictions (as recorded in PR description); do not relax gates.
- No independent forward challenger sample was newly verified this iteration. The separate non-production Web Shadow scorecard's previously documented 85 scored, 46 correct is NOT a forward champion comparison.

## Priority queue
1. Check exact-head CI for 50cc6f7b50f5c2e826579d0e7eef75f6e6fbe68a; if I001 persists, execute `ruff check --fix --diff tests/test_research_calibration_signflip_real.py` in an environment with Ruff and apply exact formatter output, then rerun CI.
2. Audit identity conflicts and official source provenance in PR #428; keep mismatches quarantined.
3. Prespecify leave-one-date-out sensitivity of 55 paper predictions: compare baseline vs fixed-half Brier and log loss, report 15 signed changes and worst-case removal; exploratory only, untouched forward holdout.
4. Collect future pre-start paired champion/challenger predictions with immutable provenance and time-ordered settlements before any promotion.

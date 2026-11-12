# Iteration 11 — repeat Ruff failure and import grouping adjustment (2026-11-10 UTC)

Status: **research-only repair attempted; exact-head verification pending**. No champion change, no prospective performance claim.

## Actual checks and evidence
- Queried main, open PRs #428 and #429, recent workflows, and the immutable non-production scorecard. PR #429 head prior to this iteration: `a7167f6bd71c4072cd42d74c6de3d1bec28e15dd`.
- Inspected CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42744331513, job `129592710149`. Pytest **1,330 passed**, 2 deprecation warnings. Ruff **failed I001** at `tests/test_research_calibration_signflip_real.py:6`; overall CI failed. Previous insertion of a blank line between `import pytest` and `from scripts...` did NOT fix the failure.
- Read the actual test source and `pyproject.toml` Ruff configuration. Hypothesis: Ruff is classifying the `scripts` namespace as third-party rather than first-party, so a separator between these imports is rejected. Removed that separator in research-only test file. Commit `77769e8d414c3a75a4909b282c4066dbc81b4043`.
- Repro command: `ruff check . && pytest -q tests/test_research_calibration_signflip_real.py && pytest -q`. Local Ruff installation was attempted but failed due to DNS/network restrictions; no successful exact-head CI has yet been observed. If I001 persists, inspect Ruff's actual `--diff` suggested ordering and consider explicit `known-first-party = ["scripts"]` in a scoped Ruff config after checking all imports.
- Latest WTA Web Shadow Result Acquisition workflow https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42742365551 succeeded as a job, **not as evidence of a new verified settlement**. PR #428 still documents 16 inspected pending, one finished captured, 13 unmatched, and two player identity conflicts. Do not merge automatically or bypass identity gates.
- Main Web Shadow source remains non-production: 88 settled, 85 scored, 46/85 correct, Brier 0.251461, log loss 0.696908. Independent forward challenger settlement N was not freshly verified in this run; last documented N was zero.

## Next executable priority
1. Inspect exact-head CI for `77769e8...`, fix any Ruff failure using observed formatting output, verify all tests.
2. Run tournament/date leave-one-cluster-out sensitivity on 55 historical paper predictions without changing the selection rule or touching holdout; record per-cluster deltas and failure cases.
3. Investigate PR #428 identity conflicts with source-level proof, without weakening trust gates; rerun verified forward settlement aggregate.

## Research context
The previous 15-date-cluster sign-flip analysis is exploratory only; exact enumeration does not overcome temporal dependence, small cluster counts, or reuse of the same matches. See MacKinnon, Nielsen & Webb (2023), https://doi.org/10.1002/jae.2969, for why small/unbalanced clusters make inference fragile. New model-comparison tests require fresh, precommitted matches.

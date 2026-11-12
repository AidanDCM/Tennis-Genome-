# Iteration 22 — execute sensitivity through established PR CI (2026-11-10)

**Research only; no champion or settlement modification.**

## Audited evidence
- Main result manifest blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` still references Hong Kong result, not unmerged PR #428's Chennai result.
- PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f` remains open; 16 pending inspected, 1 finished captured, 13 unmatched, 2 held identity mismatches. In particular Hong Kong LS031 predicts Alycia Parks/Alexandra Eala while provider shows Emerson Jones/Alexandra Eala; never infer a settlement from the match ID alone.
- PR #429 previous head `b6921deff88e88ceb9a72f44678953620b940e7b`: associated PR CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42826747046 passed Ruff and pytest, but ran only the standard test job. It did not run the standalone sensitivity script or publish its JSON.
- Research script blob `611daf2912a5c7fdb19e9405cccafea487a68e5b`; calibration script blob `38dddd21f9bf7edfa6e7c6d4c88d256ca345e6c8`. The standalone workflow exists on the research branch, but has no observed execution in the inspected PR CI runs. Direct local Git clone failed with `Could not resolve host: github.com`.
- Main non-production WTA Web Shadow scorecard: 88 settled records, 85 completed/scored, 46 correct, Brier 0.2514610585, log loss 0.6969082733. This is not the independently qualified forward challenger scorecard.

## Implemented execution repair
Commit `2c0840c8b9e370f873233d4d6c345322e9b27d5b` adds a read-only execution step to the already-running PR CI workflow, with `set -o pipefail` and named `research-date-cluster-sensitivity` JSON artifact upload. A script failure now fails CI instead of silently leaving an empty result. No production code changed.

## Prespecified experiment
H0 diagnostic: fixed slope 0.5 Brier/log-loss improvements are concentrated in a single date cluster. Compare original locked probabilities with fixed 0.5 and chronology-selected adaptive slope on exactly the script's 55 eligible retrospective rows (15 UTC dates). Leave each date out **without refitting**. Record all 15 rows, min/max paired improvements, number of nonpositive improvements, sample IDs, and provenance. Success diagnostic: both fixed improvements strictly positive in all 15 exclusions; still **not** independent validation. Failure: any nonpositive date-exclusion improvement, scorecard reproduction failure, CI failure, or missing artifact. Never select or promote using this repeatedly examined dataset.

Reproduce on checked-out research head: `ruff check . && pytest -q && python scripts/research_calibration_signflip_real.py --repo-root . > date-cluster-sensitivity.json`. Exact-head CI must be checked separately.

## Research contrast
Pic et al. (published 2025-03-13), https://doi.org/10.5194/ascmo-11-23-2025 : proper scores characterize different forecast defects; controlled simulations and weather case study, R source published under open-source repository, paper CC BY 4.0. Adapt complementary Brier/log-loss diagnostics, not its multivariate wind-specific code. Waghmare & Ziegel (2026), https://doi.org/10.1146/annurev-statistics-042424-050626 : proper scoring-rule theoretical review, CC BY 4.0; does not validate any tennis-specific calibration slope. Neither provides comparable tennis winner accuracy or supports reusing the historical test sample for promotion.

## Prioritized queue
P0 inspect CI for this ledger's exact head and download 15-date artifact; if failing, diagnose and repair. P1 audit capture workflow freshness and adjudicate both identity mismatches with original WTA source bytes, without relaxing identity gates. P2 produce paired locked prospective champion/challenger evidence with qualified N, Brier, log loss, coverage and date/surface breakdown. P3 only after sufficient prospective N, test simpler calibration against baseline with untouched holdout.

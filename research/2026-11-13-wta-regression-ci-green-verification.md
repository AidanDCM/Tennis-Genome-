# 2026-11-13 WTA regression exact-head CI verification

## Pinned baseline, hypothesis, and executed comparison
Main at PR #479 baseline: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Tested PR head: `0db0353972244b6cf17e83e37465a2f713267140`. Source module blob on main: `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`; nine-case test blob on tested head: `0f69b0a613ac26efa44ca45956a7ecbd29e7fb6d`.

Hypothesis: nine synthetic identity/round regression cases can pass along with the full repository CI checks, without changing production settlement code. Baseline: previous head `9dce708da033` CI #43353580672 had 1319 passing pytest cases but failed Ruff E501. Prespecified success: Ruff success and pytest success on the *same exact head*, all negative identity controls intact. Failure: either check fails, or any identity-negative control accepts a match.

## Executed evidence (not inferred)
Queried connected GitHub commit workflow runs for `0db0353972244b6cf17e83e37465a2f713267140`: run [#43367599685](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43367599685), completed SUCCESS. Queried run jobs: job `131695571776`, completed SUCCESS, Ruff step SUCCESS, Pytest step SUCCESS. Fetched actual job log; confirmed invocation `ruff check . --output-format=concise > ruff.txt 2>&1`, then `pytest > pytest.txt 2>&1`, and uploaded diagnostic artifact [#14010936927](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43367599685/artifacts/14010936927). Because command outputs were redirected to files, the job log does **not** expose an independently counted pytest denominator or Ruff's textual summary; the successful steps establish exit-zero, not a fresh assertion of 1319 count. No new local pytest was executed. Exact tested commit is the PR head before this ledger-only commit.

Read test file at tested SHA and confirmed nine distinct `test_*` methods, covering legacy numeric/textual rounds, exact ID, wrong player, missing ID, duplicates, wrong event. No production code change or settlement action.

## Current evidence and limitations
The previously reported non-production WTA Web Shadow scorecard (not refreshed in this run) had 47/86 correct, Brier 0.251322, log loss 0.696621, 15 pending. Fixed-0.5 baseline Brier 0.25, log loss ~0.693147. Production champion checksum and qualified forward N not reverified. Twelve source-row candidate pairs remain diagnostic only; pre-start provenance and tournament identity unadjudicated. This ledger commit itself has not been tested by the successful workflow above.

## External methods, contrary evidence, and license scope
- Rohde et al., March 2025, [Multi-Layer Privacy-Preserving Record Linkage with Clerical Review](https://doi.org/10.18420/BTW2025-18): layered human review improved linkage on their own real-world data. Transferable concept: review ambiguous WTA identities without automatic settlement; their populations and metrics differ. No software imported or code license established.
- Binette et al., 2024, [How to Evaluate Entity Resolution Systems](https://arxiv.org/abs/2404.05622): entity-centric reference labeling, representative samples, and error-root-cause analysis; simulation and inventor-name datasets, not tennis. Open-source implementation linked in paper but its license was not checked; no code reused.
- Contrarian: 2025 [JAMIA Open systematic review](https://doi.org/10.1093/jamiaopen/ooaf002), five eligible real-world studies, found name-based deterministic matching can be precise yet miss legitimate matches; cannot extrapolate reported rates to WTA. Supports measuring false negatives alongside strict false-positive safeguards.

## Reproduction
From tested SHA: `git checkout 0db0353972244b6cf17e83e37465a2f713267140 && python -m pip install -e . && python -m pip install ruff==0.16.7 pytest && ruff check . && pytest -q`. Workflow used its own pinned dependencies; see exact run logs for authoritative environment.

## Prioritized next executable experiments
1. Verify any CI triggered by this ledger-only head and retain draft PR #479 for review, no merge.
2. Refresh main champion manifest, verified forward denominator, workflow schedules, and WTA shadow scorecard.
3. Build diagnostic-only round/identity mismatch classification with adversarial negative controls and source IDs; independently adjudicate twelve historical candidates, no settlement writes.
4. Improve prospective acquisition/coverage and pre-start evidence capture; preserve immutable predictions.
5. Only then preregister chronological paired Brier/log-loss/calibration tests versus frozen champion and fixed-probability baseline with untouched holdout.

# 2026-11-10 iteration 17: exact Ruff diff repair

## Executed evidence
- PR #429 head inspected: `331eb7568eb945a0a21f934980401b9d9d894f4f`, draft, research branch `research/2026-11-09-calibration-audit`; base main `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- Inspected CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42784843116, job 129723382261. Final outcome **failure**; Ruff I001 at test line 7, pytest **1330 passed, 2 warnings**.
- CI-generated `ruff check --select I --diff tests/test_research_calibration_signflip_real.py` explicitly requested removal of one extra blank line between `import pytest` and `ROOT = ...`. Applied exactly that one-line deletion, commit `49b1611ffe9258846a723332b6c9b20a2e5738a7`, resulting file blob `1affb48d05a589367cb758c28f873878f362e474`.
- Verification command: `ruff check . && pytest -q tests/test_research_calibration_signflip_real.py && pytest -q`. No exact-head CI workflow was returned immediately by the commit-run query; **do not claim green**. CI must be inspected when available.
- Research script blob `09043310c8d937c531a4f7d9fcbc871292c4a985`; non-production scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`. Historical scorecard 85 scored, 46 correct, Brier 0.251461, log loss 0.696908 (not new forward validation).
- PR #428 remains open; snapshot 16 pending inspected, 1 finished captured, 13 unmatched, 2 identity conflicts. These are **not** qualified prospective settlements.

## Research and falsifiable comparisons
- Bunker et al. (first online 2023-11-10), https://doi.org/10.1177/17543371231212235: expanding training window, 14 ATP test years 2007–2020; some simple statistical classifiers beat basic Elo in their specific evaluation. Published article; code license and reproduction rights not verified; no code copied. ATP-only comparisons do not transfer automatically to WTA. Any prohibited external inputs are excluded.
- 2026 unified benchmark https://www.mdpi.com/2813-2203/5/3/22 compares rating, classical and neural models under a shared temporal split and reports modest incremental gains from complexity. Dataset and protocol not equivalent to Tennis Genome, and feature availability must be checked at match start. No code copied; license unverified.
- Hypothesis for next **exploratory** sensitivity: fixed-half calibration has positive paired Brier and log-loss improvements for all 15 leave-one-date-cluster-out subsets, relative to unchanged probabilities on the same 55 observations. Report all exclusions, min/max and sign counts; any nonpositive exclusion falsifies stability criterion. This is **not** a prospective significance or promotion test. Keep final holdout untouched.

## Prioritized executable queue
1. Inspect exact-head CI for `49b1611`; if lint fails, use machine-generated diff, not guessed formatting. Confirm pytest and Ruff independently.
2. Run read-only leave-one-date-cluster-out sensitivity for fixed-half versus original, with sample IDs and date counts; keep adaptive result exploratory.
3. Audit PR #428 identity mismatches and freshness of capture/settlement workflows; do not relax identity, timing or provenance.
4. Acquire new pre-start locked prospective pairs and independently verified results before evaluating promotion.

No champion or settlement change. No predictive gain claimed.

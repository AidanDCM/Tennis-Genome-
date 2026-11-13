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

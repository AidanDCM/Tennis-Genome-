# Iteration 19 — 2026-11-10: exact-head CI and experiment execution trigger audit

Research-only. No model, predictions, settlement, champion, or trust gates changed.

## Verified source and execution
- PR #429 draft head at start: b772e2d0f337dd1e87710e91717f8875bdf22d47; main base 8af76720a6291b166263fa1cd8191504f84ed6b6.
- Exact-head CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42801143407 completed **success** on b772e2d0; job 129778667471 Ruff and pytest steps success. Output was redirected to ci-diagnostics artifact 13756246688; logs do not expose per-test counts.
- Verified source script blob 611daf2912a5c7fdb19e9405cccafea487a68e5b; test blob 0148c013084e98cf70b7bafbd6ea6eddc451a2e7. Script computes 15 leave-one-UTC-date exclusions on the 55 chronological evaluation IDs and preserves frozen original probabilities.
- Research workflow originally triggered only when the script/workflow changed, so test-only and ledger commits did not launch sensitivity output. Fixed workflow path trigger in commit c7bc2974e16b55db326a71d2adea2a1050fa40cb; added tests/test_research_calibration_signflip_real.py. No result run was returned immediately after this commit; do not claim numerical output.
- Local git ls-remote failed with DNS error: Could not resolve host github.com. Therefore no local full-data experiment was run. Exact commands: `python scripts/research_calibration_signflip_real.py --repo-root .`, `pytest -q tests/test_research_calibration_signflip_real.py`, `ruff check scripts/research_calibration_signflip_real.py tests/test_research_calibration_signflip_real.py`.

## Prespecified comparison
Population: same 55 historical eligible WTA matches, 15 UTC dates. Fixed half-slope and adaptive slopes against frozen original probability. For each UTC date exclude that cluster, report removed/retained N, paired mean Brier and log-loss improvements; success only if both fixed-half improvements remain positive for all 15 exclusions. Failure if any nonpositive; no significance claim even on success. This is influence sensitivity, not independent refitting, not a new holdout.

## Operational gate and evidence
- Main non-production scorecard blob 60082a6292087e2b6e902faca79f2f4c847d8fdb: 46/85 scored correct, Brier 0.2514610585, log loss 0.6969082733; 88 settled records total, distinct denominator.
- PR #428 remains open, with 16 inspected pending, 1 finished result, 13 unmatched, 2 player-identity conflicts; must not assume matches. No refreshed qualified prospective count verified.
- PR #429 draft; no merge or promotion.

## Research / contrary evidence
- Loveday, Taggart & Khanarmuei (2024), https://doi.org/10.1175/WAF-D-23-0201.1, peer-reviewed binary probabilistic forecasting evaluation using Murphy diagrams and proper scoring rules. Weather rather than tennis; no implementation copied, publisher reuse license requires review. Suggests a future prespecified probability-threshold diagnostic without optimizing thresholds on test observations.
- Ferro (2017), https://doi.org/10.1002/qj.3115, observation error can distort forecast ranking even with proper scores. Weather examples; direct adaptation is to quantify exclusion/coverage caused by uncertain result identity, not silently assign labels. No code imported.
- Pic et al. (2025), https://doi.org/10.5194/ascmo-11-23-2025, CC-BY-4.0 open access, complementary proper scores; multivariate weather application not directly comparable to binary tennis.

## Negative results and queue
- No new prospective performance or statistical superiority established.
- P0: inspect GitHub sensitivity workflow for commit c7bc2974 and capture complete 15-date output; if no run, inspect workflow trigger permissions and dispatch/modify narrowly.
- P0: inspect source-level two identity conflicts and freshness of acquisition workflows; preserve provenance, pre-start and frozen champion gates.
- P1: use genuinely new, locked prospective pairs for Brier/log-loss and winner accuracy with confidence intervals, tour/surface/time coverage and selection audit.
- P2: only after qualified N grows, prespecify one simple surface-aware Elo ablation with untouched final holdout.

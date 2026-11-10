# Iteration 10 — exact-head CI diagnosis and import-order repair (2026-11-09)

Status: **research-only code repair**. No champion/model changes, no newly qualified forward observation, no demonstrated forecasting gain.

## Executed audit and failure evidence
- Checked current main repository, open PRs #428 and #429, WTA non-production scorecard, and recent GitHub Actions. PR #429 head before repair: `3797212e79c72a4aa41b31c7cd21b32712cf6359`.
- Inspected completed exact-head CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42737563945, job `129570410688` (failure). **Pytest actually passed 1,330 tests** with two deprecation warnings. Ruff failed with exactly one `I001` at `tests/test_research_calibration_signflip_real.py:6`. This corrects the previous ledger's uncertainty: seven new real-scorecard tests executed successfully on this head; CI as a whole failed solely because of Ruff.
- Root cause: missing blank line between third-party `import pytest` and first-party `from scripts.research_calibration_signflip_real import evaluate`.
- Applied minimal repair to the isolated PR branch: inserted that separator, commit `2f081394da56e9f1136ca684a4b2a1e1fb27c465`. Repro: `ruff check . && pytest -q tests/test_research_calibration_signflip_real.py && pytest -q`.
- **Exact-head CI for commit `2f081394...` is not yet confirmed.** Do not call it successful until GitHub run logs verify it.

## Current evidence and constraints
- Main's immutable non-production WTA Web Shadow scorecard: 88 settled records, 85 completed/scored, 46 correct / 85 (54.12%); Brier 0.251461; log loss 0.696908. No source record was altered.
- Exploratory calibration comparison still uses 55 previously collected WTA matches in 15 date clusters. Sign-flip fractions for Brier: adaptive 0.3297, fixed-half 0.2145. No confirmatory advantage, and winner accuracy is unchanged by positive-slope calibration.
- Forward independent challenger settlement count **not revalidated from a fresh aggregate artifact this iteration**. Last documented aggregate had zero; do not claim the current count is zero without rerunning the gate.
- PR #428 remains open and its identity conflicts remain unresolved. A successful result-acquisition workflow does not prove valid new settlements.

## Methodological reference and counterevidence
- MacKinnon, Nielsen & Webb (2023), https://doi.org/10.1002/jae.2969: with few or unbalanced clusters, nominal confidence intervals can mislead. Their regression-based methods cannot simply be relabeled as valid inference for selected tennis forecasting models. No external code copied.
- A significant-looking historical comparison after repeated candidate selection would be susceptible to selection bias; treat current results as exploratory until a locked prospective evaluation is available.

## Next executable queue
1. Verify exact-head CI for `2f081394...`; inspect Ruff and pytest logs, repair if necessary.
2. Implement read-only leave-one-tournament-out and leave-one-date-out influence analysis on the same 55 locked paper predictions; report worst-case changes, not cherry-picked averages.
3. Audit #428's two identity conflicts and result acquisition evidence without relaxing identity/timing/provenance checks; increase genuinely prospective settled N.
4. Run prospective champion-versus-challenger comparisons only after independent, pre-start-locked settlements exist. Never promote automatically.

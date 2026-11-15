# Iteration 18 — 2026-11-10: date-cluster influence audit

Status: research-only; do not merge/promote. No production champion, source prediction, result, or trust gate changed.

## Verified execution and code
- Prior exact-head CI: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42792422379 ; test job 129748925485 **success**, Ruff and pytest steps both success. This verifies earlier head d28260bae51ebebecc24f54e2ba0a94dff1ce2e6, not the changes below.
- Study source: scripts/research_calibration_signflip_real.py blob 09043310c8d937c531a4f7d9fcbc871292c4a985.
- New experiment code commit a7fb192b010255baac3217a454d2743fddb3c28b; new test commit 6c91b9f821eeb514f3d39e4a42cdc6ea878dcf19.
- Commands: `python scripts/research_calibration_signflip_real.py --repo-root .`; `pytest -q tests/test_research_calibration_signflip_real.py`; `ruff check scripts/research_calibration_signflip_real.py tests/test_research_calibration_signflip_real.py`.
- On immediate inspection, no workflow runs were returned for 6c91b9f821eeb514f3d39e4a42cdc6ea878dcf19. **New experiment output and exact-head CI not yet independently verified.**

## Prespecified hypothesis
Fixed half-slope calibration improves paired mean Brier and log loss versus original locked probability on the same 55 historical eligible WTA matches, and its paired improvement stays positive when any one UTC date cluster is excluded. Failure: at least one exclusion reverses either improvement, or no complete 15-cluster output. This is *influence sensitivity*, not independent out-of-sample validation or leave-one-cluster-out retraining.

## Implementation
For both the adaptive and fixed-half controls, reconstruct original locked evaluated probabilities and paired score differences. For each of the 15 UTC dates, remove all rows from that date and report date, removed N, retained N, and retained mean paired Brier/log-loss improvement. No refit and no model selection. Tests assert unique dates, complete partition (sum excluded N = 55), retained N and finite bounded score differences. The baseline is the unchanged frozen Genome probability. Selection/forward evidence remains exploratory.

## Operational evidence and gates
- PR #429 research remains draft; PR #428 result acquisition remains open. PR #428 records 16 inspected pending, one finished result, 13 unmatched, two player-identity conflicts. Conflicts must not be automatically settled.
- Main scorecard blob 60082a6292087e2b6e902faca79f2f4c847d8fdb: historic non-production 46/85 correct, Brier 0.25146106, log loss 0.69690827; 88 settled records are a different denominator.
- Last independently checked forward challenger aggregate: zero settled, **not refreshed this iteration**.
- Immutable champion and pre-start identity/provenance/timing checks were not modified.

## External research / contrary evidence
Qiu et al. (2024), https://arxiv.org/abs/2405.20400: cluster-based validation can expose overfitting from dependent groups; their NICc approximates leave-one-cluster-out *model refitting* and is not equivalent to this fixed-prediction deletion diagnostic. Open preprint, no code imported; license of implementation not audited.
Roberts & Leutbecher (2024), https://arxiv.org/abs/2410.06162: evaluation/calibration inconsistencies can arise when reference climatology is estimated from finite samples; warns against calibrating and verifying on shared data. Weather anomaly population not directly comparable to tennis.

## Negative results and queue
- No new forecasting advantage or prospective observation confirmed.
- P0: inspect exact-head CI, debug any failure; retrieve 15-row influence output and report min/max, number of sign reversals for both scores.
- P0: audit result-acquisition identity conflicts and provider provenance; increase qualified forward settlements without weakening gates.
- P1: independently validate new locked challenger against genuinely future results, paired champion baseline; track accuracy denominators, Brier, log loss, uncertainty and coverage.
- P2: if qualified N grows, compare one simple surface-aware Elo ablation against champion with untouched final holdout.

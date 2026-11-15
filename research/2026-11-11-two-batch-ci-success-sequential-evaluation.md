# 2026-11-11 — Two-batch CI verification and sequential evaluation research

## Actual execution evidence
PR #441 head `d4eba1dc4de0aa45bc9f7b52fd8edc1a4e45b07d` (draft).
GitHub Actions run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43022557628 completed SUCCESS for PR commit; job `test` had Ruff SUCCESS, Pytest SUCCESS, diagnostics upload SUCCESS. Exact job steps retrieved through GitHub API. This supersedes the earlier failed run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43014590482 (fixture path mismatch, Ruff F541), which remains an auditable negative result. The connector returns step conclusions, not per-test names/counts or full logs; do not infer a precise pytest pass count for this run.

Main scorecard blob SHA `60082a6292087e2b6e902faca79f2f4c847d8fdb`; active-results manifest blob SHA `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`. Current active result points to Hong Kong final; 16 pending in prior scorecard. PR #428 still open; review before acquisition resumes. No production-forward aggregate was run and qualified N remains unverified.

## Prespecified experiment and interpretation
H1: synthetic two-batch settlement test passes exact-head CI while maintaining first batch settlement/receipt bytes, two scored contributions and safe replay rejection. H0: test fails. Comparison: existing one-batch tests. Synthetic sample IDs `web:wta:test:1` and `web:wta:test:2`; workflows 9001/9002; artifact IDs 7001/7002. Success: Ruff and pytest success on exact PR head. Observed: SUCCESS. CI supports integration test execution but not real-world settlement completeness or historical match provenance. No model improvement claim.

Reproduce: `ruff check tests/test_apply_web_shadow_settlement_batch.py && python -m pytest -q tests/test_apply_web_shadow_settlement_batch.py` on PR #441 head; full CI `python -m pytest -q`. Exact-head source: https://github.com/AidanDCM/Tennis-Genome-/blob/d4eba1dc4de0aa45bc9f7b52fd8edc1a4e45b07d/tests/test_apply_web_shadow_settlement_batch.py .

## Research rotation: sequential comparison (not model tuning)
Henzi & Ziegel, *Valid sequential inference on probability forecast performance* (2022), https://doi.org/10.1093/biomet/asab047 (published Biometrika, 2022; correction 2022), studies anytime-valid e-values for binary forecast comparison, with weather examples, not tennis. Frazier & Poskitt, *Sequential Scoring Rule Evaluation for Forecast Method Selection* (2025 preprint), https://arxiv.org/abs/2505.09090, studies sequential score comparisons in simulations; preprint status and assumptions require checking. Grob et al. (2026 preprint), https://arxiv.org/abs/2608.23064, evaluates sequential calibration for inflation forecasts; different population and horizon. Adaptation candidate: preregister one paired champion-vs-challenger Brier comparison on newly locked chronological outcomes, with a valid sequential stopping rule and a minimum evidence floor. Contrary consideration: e-values do not repair mislabeled outcomes, selection bias, or unmatched model populations. No external code/datasets reused; licenses not relevant to code reuse.

## Queue and blockers
1. Human-review PR #441 after successful CI; do not autonomously merge.
2. Review and safely resolve PR #428, verify official WTA identity/round/time/provenance, and restore acquisition without relaxing gates.
3. Recompute independent qualified forward N and paired loss after capture resumes; do not substitute 85 historical shadow matches.
4. On sufficient locked chronological data, preregister simple no-change champion vs Elo and calibration shrinkage as a challenger, with untouched final holdout and multiplicity control.

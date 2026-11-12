# Settlement replay and corruption regression — 2026-11-11

## Baseline and evidence
Main commit: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
Source: [publisher](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/scripts/apply_web_shadow_settlement_batch.py), blob `eeb98a1259b61dfc32aaf177da31d3622b9a70f4`.
Existing [test fixture](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/tests/test_apply_web_shadow_settlement_batch.py), blob `1e0b489d9685451ddb9bd4ac3329e245f0628e26`.
Synthetic sample: `test-slate`, `web:wta:test:1`, artifact run `9001`; never production evidence.

## Prespecified falsifiable hypotheses
H1: Applying the same valid batch twice rejects the second application and leaves scorecard, settlement and receipt bytes unchanged.
H2: Modifying the artifact ZIP after computing its SHA-256 rejects publication without writing scorecard, settlement or receipt.
Success: both new pytest cases pass with no mutation, and existing CI passes. Failure: exception absent, wrong error, or byte-level drift.
Comparison: publisher's current single-application happy path versus replay and corrupt-artifact paths.

## Implementation and reproducibility
Branch: `research/2026-11-11-settlement-replay-regression`.
First test commit: `670539c4bee79101ccd94b6141661c064fb0c588`.
Run `python -m pytest -q tests/test_apply_web_shadow_settlement_batch.py`; run `ruff check tests/test_apply_web_shadow_settlement_batch.py`.
Exact-head GitHub CI must be checked after PR creation; no local checkout was possible because the execution container could not resolve `github.com`.
Tests use only synthetic records, with unchanged trust gates.

## Research
Ferro (2017), https://doi.org/10.1002/qj.3115 — noisy observations can distort probabilistic score rankings; peer-reviewed weather/verification methods, not comparable tennis outcomes. No code reused; license of underlying paper not assumed.
Pohle, Zahn and Lerch (2026), https://arxiv.org/abs/2605.03997 — simultaneous uncertainty bands for forecast comparisons; preprint, bootstrap assumptions must be verified, not evidence of tennis model improvement. No code reused.

## Limitations and next experiments
These tests are single-batch replay/corruption regressions, **not** a two-distinct-batch replay or a complete end-to-end settlement publication proof.
Next: build two independent synthetic locked predictions with distinct slate and match IDs; apply batches chronologically and verify first settlement durability and no metric drift. Then inspect invocation of publisher and acquisition PR #428. Do not backfill or promote production models.

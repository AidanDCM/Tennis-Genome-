# Iteration 40 — Settlement publisher discovery (2026-11-11)

Base main SHA: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
Source blob: `scripts/apply_web_shadow_settlement_batch.py` SHA `eeb98a1259b61dfc32aaf177da31d3622b9a70f4`.
Scorecard blob: `web-shadow/scorecard.json` SHA `60082a6292087e2b6e902faca79f2f4c847d8fdb`.

## Falsifiable hypothesis
Contrary to the implication that no durable publisher is known, main contains an explicit batch artifact application function that writes settlements, recomputes the canonical scorecard, validates it and rolls back on exception. Baseline: artifact-only workflow. Success: all four stages exist in source; failure: missing any stage. This is a **source-contract audit**, not an executed two-batch integration replay.

## Executed checks
Using GitHub connector fetch_file on main, tested 9 boolean assertions in JavaScript on the exact source and scorecard: publisher function exists; scorecard write; validation after write; pending-only binding; duplicate prediction rejection; batch receipt write; rollback restoring original scorecard bytes; 88 historical settlements recorded; production_eligible false. **9/9 passed**. The publisher exists in `scripts/apply_web_shadow_settlement_batch.py`. It copies settlement files, creates durable batch receipts, recomputes scorecard metrics, writes scorecard and validates it; exception handler restores scorecard bytes and removes copied files/receipts. The batch producer itself does not publish; application is a separate stage. We have **not** verified its invocation workflow, actual deployment, or full two-batch replay.

## Reproduce
`python -c "from pathlib import Path; s=Path('scripts/apply_web_shadow_settlement_batch.py').read_text(); assert 'def apply_web_shadow_settlement_batch(' in s; assert '_write_json(scorecard_path, scorecard)' in s; assert 'scorecard_path.write_bytes(original_scorecard_bytes)' in s; print('publisher-contract PASS')"`

## Observed scorecard (non-production WTA Web Shadow only)
88 settled records, 85 eligible scored, 46 correct, 54.1176% accuracy, Brier 0.251461, log loss 0.696908, pending 16. Paired Elo comparison only N=78: Genome 41/78, Elo 42/78; Genome Brier 0.252433 vs Elo 0.259745, log loss 0.698682 vs 0.722719. These are descriptive, not independent superiority. Qualified forward production N not refreshed; prior reported 0.

## Research references and limits
- Ferro (2017), [Measuring forecast performance in the presence of observation error](https://doi.org/10.1002/qj.3115): observation error can reverse forecast rankings. Weather/tornado/icing examples, not directly transferable performance; no code imported.
- Burt, Shen & Broderick (2025), [Consistent Validation for Predictive Methods in Spatial Settings](https://proceedings.mlr.press/v258/burt25a.html): evaluation sampling mismatch can invalidate classical validation. Spatial setting differs from tennis; adapt sampling/coverage audits, not claimed scores. Open-access proceedings; no code imported.
- Pic et al. (2025), [Proper scoring rules based on aggregation and transformation](https://doi.org/10.5194/ascmo-11-23-2025): multiple complementary scores needed; CC BY 4.0, R code linked in paper; no code imported. Weather population differs from tennis.

## Negative evidence and queue
1. **Highest priority:** locate actual artifact-application workflow and identify whether it runs on main, uses reviewed PR, and records retained SHA receipts. Inspect historical applied batches. This audit cannot establish successful operation.
2. Run synthetic two-batch apply/replay integration test on isolated temporary repository; assert second batch retains first, duplicate/replay fails closed, corruption rolls back without mutation.
3. Review outstanding result-acquisition PR #428, resolve provenance and identity discrepancies; do not bypass trust gates.
4. Restore genuinely qualified prospective capture, then fixed paired champion/challenger Brier, log loss, calibration and time-ordered evaluation with protected final holdout.

No predictions, settlements, model or trust gates modified. No promotion or merge authorized.

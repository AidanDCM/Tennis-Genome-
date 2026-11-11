# 2026-11-11 — Two-batch settlement CI failure and fixture correction

Repository: AidanDCM/Tennis-Genome-; PR #441 (draft).
Initial head: `6b31a4f7141da88fc1a10280dcbd317e227c149a`.
Failed exact-head workflow: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43014590482
CI observations: Ruff F541 at test line 118; pytest 1 failed, 1308 passed, 2 warnings. The new two-batch test failed during fixture setup: the second fixture still wrote `web-shadow/results/test.json` while the test copied `web-shadow/results/test-2.json`. Thus the two-batch publication hypothesis was NOT evaluated by this failed run.
Correction commit: `29376910031b9a1912b77bba400b7fc4be18aed8` (test file only): parameterize fixture result filename with `stem` and remove redundant f-string. No production evidence or model changes.

## Preregistered test
Hypothesis: sequential application of two independent synthetic completed batches retains both canonical scorecard contributions, preserves first settlement/receipt bytes, and rejects replay of either batch without mutation.
Baseline: existing single-batch replay and corruption tests.
Population: two synthetic predictions in distinct slates; no real results.
Success: exact-head Ruff and pytest success including the new integration test. Failure: any mutation, rejection of valid second batch, or failed test. No accuracy/model claim.
Reproduction: `python -m pytest -q tests/test_apply_web_shadow_settlement_batch.py`; `ruff check tests/test_apply_web_shadow_settlement_batch.py`; full CI `python -m pytest -q`.
Source: https://github.com/AidanDCM/Tennis-Genome-/blob/29376910031b9a1912b77bba400b7fc4be18aed8/tests/test_apply_web_shadow_settlement_batch.py
Research: Ferro (2017), https://doi.org/10.1002/qj.3115, shows outcome-observation error can distort proper scores. It uses meteorological case studies, not tennis, and offers no directly comparable accuracy; methodological adaptation: keep strict identity and immutable outcome checks rather than adjusting model probabilities to questionable settlements. Jolliffe (2017), https://doi.org/10.1002/met.1626, provides contrary framing: a score optimized against noisy observations need not reward forecasts of the latent true event. Neither external code nor dataset was imported; reuse licensing not evaluated because no reuse occurred.

## Negative results and queue
1. Inspect exact-head CI after correction; repair any remaining failure.
2. Validate publisher durability for two distinct batches, including receipts and replay.
3. Review acquisition PR #428 and official identity/round/timing/provenance gates; restore qualified prospective capture after human review.
4. Recompute forward-qualified N and paired Brier/log loss before any model ablation; preserve untouched final holdout.

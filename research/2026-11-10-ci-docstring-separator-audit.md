# 2026-11-10 research CI and prospective evidence audit (iteration 14)

## Exact repository evidence
- Draft PR #429 head before change: `ba076cc16caaac04b0515fac3bb0ac1b4991ed8e`; base main `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- CI [42763504333](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42763504333), inspected job 129654492726: 1330 pytest passes, two pre-existing escape-sequence warnings; Ruff I001 at `tests/test_research_calibration_signflip_real.py:6:1`; overall failed. GitHub step status "success" for Ruff reflects shell redirection and must not be mistaken for lint success.
- Source blob before edit `af8134335017ba29fab2ebc0b4a19d66ba81206c` lacked an empty line between closing module docstring and first import. Research-only formatting edit added the separator; commit `d3112d21f10c0cae5f228de9709fef7f4172b182`, new blob `df3c1e5efa8918d26ec07756ecccb8d78c507823`.
- At initial post-commit check, `fetch_commit_workflow_runs` returned no PR-triggered run for this SHA. This is NOT a passing CI result.
- Local attempt: `python -m ruff --version` -> No module named ruff; `git ls-remote https://github.com/AidanDCM/Tennis-Genome-.git HEAD` -> DNS failure. Thus no local Ruff or repository-wide test execution for new commit.

## Falsifiable fix
Hypothesis: I001 originates from the missing separator after the module docstring. Baseline: previous commit fails I001; candidate: one blank line inserted, no executable semantics changed. Success requires `ruff check tests/test_research_calibration_signflip_real.py` exit 0 AND exact-head full CI success. If still failing, inspect `ruff check --diff --fix` in an isolated checkout rather than guess.

## Prior evidence, not refreshed
- Historical WTA Web Shadow **non-production** 46/85 winner hits (54.12%), Brier 0.251461, log loss 0.696908; 88 settlement rows but only 85 scored completed matches.
- Historical calibration research subset: 55 observations across 15 dates; fixed half-confidence Brier gain +0.01089 and adaptive +0.00557, with inconclusive cluster sensitivity. These are not qualified prospective challenger settlements.
- Prior PR #428 snapshot: 16 pending inspected, 1 finished result, 13 unmatched, 2 identity conflicts. This run did not newly verify the forward qualified count. No trust gates changed.

## Research comparison (sources and limitations)
- Bunker et al. (first online 2023-11-10), [DOI 10.1177/17543371231212235](https://doi.org/10.1177/17543371231212235): expanding-year evaluation, ATP 2007–2020 test years, Elo vs logistic/trees. Valuable chronological protocol; population ATP rather than our WTA shadow. Paper discusses excluded market-feature baselines; **do not adopt those inputs**. Publisher licensing applies; no code copied.
- Buhamra and Groll (2025-02-03), [arXiv 2502.01613](https://arxiv.org/abs/2502.01613): Elo-enhanced features and rolling/expanding validation on men's Grand Slams; assess Elo ablation only with pre-start ratings, surface/tour splits, and held-out evaluation. Preprint, not a reproducible Tennis Genome result.
- *A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction* (2026-07-03), [DOI 10.3390/analytics5030022](https://doi.org/10.3390/analytics5030022): temporally aligned ATP comparison; reported Elo 65.87% vs hybrid 67.52%, deep models similar to simpler models. Different population/features; not a transferable accuracy estimate. Check feature availability and licensing before adaptation.
- Contrary evidence: extra complexity has limited gains under matched protocols; prioritize simple, chronologically valid baseline and data-quality gates.

## Reproduction and queue
1. On branch `research/2026-11-09-calibration-audit`: `ruff check tests/test_research_calibration_signflip_real.py && pytest -q tests/test_research_calibration_signflip_real.py`; verify exact-head CI on commit above (or ledger-only descendant). Repair only from actual formatter diff.
2. Inspect main's current forward aggregate and PR #428 raw acquisition rows; resolve two identity conflicts using independent source IDs and provenance, not name similarity; improve verified capture/settlement coverage.
3. Prespecified leave-one-date-cluster-out fixed-half calibration Brier/log-loss differences for all 15 clusters; success only if sign remains positive for all removals and paired prospective validation later confirms a gain; failure otherwise. Report ranges and negative results, do not select clusters.
4. Future *new* locked forward sample: paired champion vs fixed challenger Brier, log loss, accuracy denominator and interval, reliability, coverage, tour/surface/time and OOD. Do not promote without review.

No champion, prediction, settlement, or identity gate was modified. No production gain claimed.

# 2026-11-10 — CI evidence audit and calibration research gate

Evidence tier: **research-only; no production promotion**. Read-only audit performed on 2026-11-10 UTC. This file records observed evidence, not a successful repair.

## Repository and exact-head observations
- Repository: https://github.com/AidanDCM/Tennis-Genome-
- Draft research PR #429: https://github.com/AidanDCM/Tennis-Genome-/pull/429 ; head SHA `3357c3bcdabea45773b98f5e9d577f59e363246f`.
- Results PR #428: https://github.com/AidanDCM/Tennis-Genome-/pull/428 ; open, head `e676c961d674ffd32d254bb96f738ae7242e211f`. Its snapshot reports 16 pending predictions inspected, 1 finished result captured, 13 unresolved, and 2 player identity conflicts. These are not qualified forward settlements.
- Exact-head PR workflow: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42751397347 — **failure**. Inspected job `129615611055` log: Ruff `tests/test_research_calibration_signflip_real.py:6:1: I001`; pytest **1330 passed, 2 warnings**. Both commands execute despite the workflow step labels showing success because their output is redirected and the enforcement step fails.
- Existing regression test blob SHA `25d89ea10ce8e434e63656088940c6bba5074e61`; research evaluation script blob SHA `09043310c8d937c531a4f7d9fcbc871292c4a985`.
- Main scorecard inspected: `web-shadow/scorecard.json`, blob SHA `60082a6292087e2b6e902faca79f2f4c847d8fdb`. Non-production only; no new qualified forward N established.

## Negative result and blocker
The most recent formatting repair has **not** fixed I001. Do not report green CI. Local `pip install ruff` attempted, but failed due to DNS resolution of the package index; no local Ruff check was executed. Avoid speculative repeated whitespace changes. Preferred next step: execute `ruff check tests/test_research_calibration_signflip_real.py --fix --diff` in a trusted environment, apply the exact machine-generated diff, and rerun exact-head CI.

## Research: calibration diagnostic counter-hypothesis
- Dimitriadis, Gneiting, Jordan (2020), *Evaluating probabilistic classifiers: Reliability diagrams and score decompositions revisited*, https://arxiv.org/abs/2008.03033. CORP/PAV calibration diagnostics can expose dependence on arbitrary bin boundaries. **Do not fit PAV to the evaluation outcomes**; fit on earlier matches only and use later locked observations.
- Gneiting and Raftery (2007), *Strictly Proper Scoring Rules, Prediction, and Estimation*, https://doi.org/10.1198/016214506000001437. Brier and log loss are proper scoring rules; accuracy alone cannot validate probability improvements.
- Contrary hypothesis: the apparent fixed-half calibration benefit is driven by a few dates or by reuse of the exploratory scorecard, not stable miscalibration. Prespecify leave-one-date-cluster-out paired Brier/log-loss differences on the same 55 existing evaluation IDs (15 UTC-date clusters), reporting minimum/maximum improvement and sign reversals, without fitting new parameters. This is sensitivity analysis, **not** independent confirmation.
- The repository declares proprietary/research-use licensing in `pyproject.toml`; external implementation code must not be copied without license review.

## Prioritized executable queue
1. Obtain Ruff's actual `--fix --diff` for I001; commit only the minimal formatting change; verify the exact PR head has green CI.
2. Audit PR #428's two identity conflicts against immutable source identities; reject uncertain matches rather than relaxing matching gates.
3. Measure qualified prospective prediction/settlement coverage, timestamp and provenance gates, and frozen champion paired N from fresh artifacts.
4. Run prespecified leave-one-date-out sensitivity on the historical 55 (negative results included), then freeze candidate and evaluate only new prospective locked observations.

No source records, frozen predictions, champion, or settlements changed in this audit. No model improvement established.

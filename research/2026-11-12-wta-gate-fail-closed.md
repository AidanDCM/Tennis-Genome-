# 2026-11-12 WTA result acquisition gate fail-closed audit

## Pre-registered operational hypothesis
When the single-proposal gate fails or is skipped, downstream acquisition must not execute. Baseline PR #457 head `0873f9674a9e97348660d3ce56c36dcba85d6481`; its ten downstream conditions used `blocked != 'true'`. Success: all ten require both gate success and explicit `blocked == 'false'`, regression test passes in exact-head CI. Failure: any downstream execution possible after a failed gate, test failure, or a weakened single-proposal rule. This is a control-flow safety test, not a model-performance experiment.

## Reproducible experiment and negative finding
A four-case truth-table check executed in Python: (success,true) old=false/new=false; (success,false) old=true/new=true; (failure,empty) old=true/new=false; (skipped,empty) old=true/new=false. Thus the old guard **fails open** when a gate failure leaves its output empty. This is a static control-flow finding; no live gate failure was induced. Reproduce: `for outcome,blocked in [('success','true'),('success','false'),('failure',''),('skipped','')]: print(outcome,blocked,blocked!='true',outcome=='success' and blocked=='false')`.

## Source and code evidence
- Main baseline `8af76720a6291b166263fa1cd8191504f84ed6b6`, prior draft [PR #457](https://github.com/AidanDCM/Tennis-Genome-/pull/457), head `0873f9674a9e97348660d3ce56c36dcba85d6481`.
- PR #457 exact-head [CI #43156795015](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43156795015) completed success, Ruff and pytest job steps succeeded. Job logs redirect actual text to diagnostic artifact `13916242406`; exact test count not yet inspected.
- [Acquisition PR #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) remains open: one proposed Chennai result, 13 unresolved, two excluded Hong Kong identity conflicts. Never bypass.
- Workflow source `.github/workflows/wta_web_shadow_results.yml` (PR #457 blob `b5809d06c1cdeb89b87f5accac80784216f76da4`), tests `tests/test_web_shadow_wta_results_workflow.py` (blob `7433d228348c4fb5cd3c85c4727e92875cfd7315`).
- Changed ten guards to require `steps.pr_gate.outcome == 'success' && steps.pr_gate.outputs.blocked == 'false'`, workflow commit `d636e2ec11a55363e738f6b4eeff0047f885efb3`; regression commit `fe5e42bcb1e415991aacfc866ce548a35f2a295f`. No change to identity, pre-start, publication, or champion logic.
- Reproduce exact-head: `python -m pytest -q tests/test_web_shadow_wta_results_workflow.py && python -m ruff check tests/test_web_shadow_wta_results_workflow.py && git diff --check`.

## Performance and evidence tier
Main's **non-production WTA Web Shadow** scorecard: 85 eligible scored / 46 correct (54.12%), Brier 0.2514610585, log loss 0.6969082733, 16 pending, production_eligible=false. Fixed-0.5 Brier=0.25 and log loss=ln(2)=0.693147. Production-forward qualified N and frozen champion checksum not refreshed. No model ablation or accuracy gain claimed.

## Research
Kleen (2024), [Scaling and measurement error sensitivity of scoring rules for distribution forecasts](https://doi.org/10.1002/jae.3056), Journal of Applied Econometrics, open access: simulations and theoretical analysis of observation error and forecast-score ranking. Distributional/continuous-outcome methods do not directly establish tennis binary performance; transferable lesson is to preserve verified observations and compare proper scores. No external code adopted; implementation license not applicable.
Weerasinghe et al. (2025), [ABC-based forecasting in misspecified state space models](https://doi.org/10.1016/j.ijforecast.2024.05.005), International Journal of Forecasting, CC BY publication: simulation and empirical state-space evaluation; contrary evidence against assuming exact complex models are always best. Not independently reproduced; no code incorporated.

## Negative results and next queue
1. Inspect exact-head CI and diagnostics of this branch; fix any failure; explicitly test gate failure, blocked, allowed in isolated workflow context.
2. Human review PR #428 and Chennai settlement provenance; no automatic merge or settlement.
3. Inspect raw stable participant identifiers for LS031 and LS020; keep exclusions.
4. Restore qualified prospective capture and independently verify immutable champion and forward settlement denominators.
5. Compare champion with fixed 0.5 and Elo on newly locked chronological matched matches, paired Brier/log loss, calibration, selective coverage and confidence intervals, untouched final holdout.

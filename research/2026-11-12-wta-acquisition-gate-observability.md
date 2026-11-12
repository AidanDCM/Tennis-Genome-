# WTA result acquisition gate observability — 2026-11-12

## Pre-registered hypothesis and scope
Hypothesis: the scheduled acquisition workflow can expose an unambiguous gate outcome when an existing result PR blocks acquisition, without changing its exclusion, publication, or identity gates. Baseline: main commit `8af76720a6291b166263fa1cd8191504f84ed6b6`, where the gate logs a message but the job may finish green. Success: four explicit outcomes, gate unchanged, regression assertions pass in exact-head CI. Failure: a missing/ambiguous status, changed gate behavior, or failed CI. This is an operational test, **not** a predictive model experiment.

## Read evidence
- Main workflow: [wta_web_shadow_results.yml](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/.github/workflows/wta_web_shadow_results.yml), blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`.
- Existing workflow tests: [test_web_shadow_wta_results_workflow.py](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/tests/test_web_shadow_wta_results_workflow.py), blob `77a317449210604e63c711a2f072bdb7ce392e93`.
- Historical blocked run: [#43147568821](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43147568821), with 11 skipped steps as previously inspected. Result proposal [#428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) remains a review blocker.
- Current main non-production scorecard [scorecard.json](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/web-shadow/scorecard.json): 85 eligible, 46 correct, Brier 0.2514610585, log loss 0.6969082733, 16 pending, production_eligible=false. No newly qualified production sample verified.

## Change and reproducibility
- Branch `research/2026-11-12-wta-acquisition-gate-observability`; first workflow commit `85eec0bfa0a9dd5163cc46cd176de5e714927f76`; regression commit `4a40b6c7593dca95dafeb71db1fff250ce48b21f`.
- Adds a step with `if: always()` after the original gate. Emits `WTA_RESULT_ACQUISITION_GATE_STATE` and a job summary with `gate_failed`, `gate_indeterminate`, `blocked_by_existing_proposal`, or `acquisition_allowed`. This last state does not imply acquisition completed.
- Adds workflow contract regression assertions, without touching any production model, result, scorecard, or existing gate conditions.
- Intended exact-head test: `python -m pytest -q tests/test_web_shadow_wta_results_workflow.py`; `python -m ruff check tests/test_web_shadow_wta_results_workflow.py`; `git diff --check`.
- Actual execution: GitHub branch creation and two file-update commits succeeded; draft PR #457 opened. Exact-head workflow lookup returned `[]` at inspection. Local `git ls-remote https://github.com/AidanDCM/Tennis-Genome-.git HEAD` failed with `Could not resolve host: github.com`. **No pytest, Ruff, or exact-head CI pass claimed.**

## Research references and limitations
- Ferro (2017), [Measuring forecast performance in the presence of observation error](https://doi.org/10.1002/qj.3115): score quality depends on observation quality. Forecasts verified against mismatched tennis identities could be misleading. Methodological analogy; not tennis data; no code adopted.
- Pagano et al. (2024), [Challenges of Operational Weather Forecast Verification and Evaluation](https://doi.org/10.1175/BAMS-D-22-0257.1): operational verification requires attention to observation coverage and process reliability. No implementation/license verified; no external code adopted.
- Both studies address evaluation reliability, not a claimed improvement in tennis win probability. No model comparison or holdout was touched.

## Negative results and prioritized next queue
1. **Unverified:** Run exact-head pytest/Ruff on PR #457, inspect job logs, and repair safely if necessary. Test blocked, allowed, and failed gate behavior in an isolated workflow run.
2. Review acquisition PR #428 and immutable Chennai settlement evidence; do not bypass existing identity or timing checks.
3. Investigate provider participant identifiers for excluded `LS031` and `LS020`; keep both excluded.
4. Restore qualified forward capture and independently refresh champion checksum and forward denominators.
5. On newly locked, chronologically paired observations, compare frozen champion with simple Elo and fixed-0.5 baselines using Brier/log loss, accuracy with uncertainty, calibration and coverage. Keep final holdout untouched.

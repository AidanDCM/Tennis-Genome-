# WTA acquisition allowed but zero selected — 2026-11-13

## Evidence scope
- Main SHA: `40bb697ec786527b7ed1a4c67d6d0a92aea17782` (verified from GitHub branch API).
- Scheduled GitHub Actions run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661 ; job `131785529846`; 2026-11-13 08:44 UTC; conclusion success.
- Source artifact: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661/artifacts/14022921157 ; artifact ID 14022921157, uploaded 24 files, ZIP SHA256 `8f55a7ed64e210af6a7161c4f602f956af06fa909d5acc8346ff5f6aee80bf56` (workflow log; artifact contents not independently downloaded).
- Main workflow: https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/.github/workflows/wta_web_shadow_results.yml ; blob `f49387bb740a664ef5a72ee850203301062dbf2a`.
- Main scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json ; blob `c9636ac9d86c256ccf241e652b9456034c451fc3`. NON-PRODUCTION WTA Web Shadow only.

## Preregistered diagnostic and baseline
Hypothesis H1: the latest scheduled acquisition is blocked before official-source fetch by an existing proposal.
Baseline: earlier concern that green Actions conclusion could conceal blocked acquisition.
Acceptance H1: gate output `blocked_by_existing_proposal` or skipped fetch step. Rejection: `acquisition_allowed` and successful fetch step.
Secondary H2: an allowed fetch produces at least one safely selected official result; success requires compiler `result_count > 0`. Reject on zero.

## Actual observed run
The job log states `GATE_OUTCOME: success`, `GATE_BLOCKED: false`, and `WTA_RESULT_ACQUISITION_GATE_STATE=acquisition_allowed`. Fetch retained official WTA sources and compile finished official WTA rows both succeeded. Fetch reported 2 indexes and 10 sources. Compiler summary:
```json
{"identity_conflict_count":2,"pending_prediction_count":15,"result_count":0,"snapshot_id":"wta-results-20261113t084426z","unfinished_prediction_count":0,"unresolved_prediction_count":13}
```
No settlement dry-run, result proposal commit, or review PR occurred (those steps skipped). H1 **rejected**; H2 **rejected**. The operational blocker is unresolved identity/round matching (13) and exact-ID conflicts (2), not a blocked proposal gate in this observed run. This does not authorize retrospective settlement.

## Executed checks
Connected GitHub reads of workflow, scorecard, Actions jobs and logs; deterministic JavaScript assertions:
```js
const rows = scorecard.slates.flatMap(s => s.predictions);
const pending = rows.filter(r => r.status === "PENDING");
const checks = [
  new Set(rows.map(r => r.match_id)).size === rows.length,
  rows.length === 104 && pending.length === 15 && scorecard.metrics.settled_match_count === 86,
  workflow.includes("steps.pr_gate.outcome == 'success' && steps.pr_gate.outputs.blocked == 'false'"),
  steps.find(s => s.name === "Fetch retained official WTA sources").conclusion === "success",
  steps.find(s => s.name === "Compile finished official WTA rows").conclusion === "success",
  steps.find(s => s.name === "Open result review PR").conclusion === "skipped"
];
if (!checks.every(Boolean)) throw new Error("audit assertion failed");
```
Six of six passed. This checks internal consistency and execution steps, not independent correctness of source-row identity. No local repository-wide pytest or Ruff executed.

## Research context and limits
- Ferro (2017), *Measuring forecast performance in the presence of observation error*, https://doi.org/10.1002/qj.3115 . Observation error can change apparent model ranking under proper scores; no direct tennis evaluation or imported software.
- Pic et al. (2025), *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, https://doi.org/10.5194/ascmo-11-23-2025 . Multiple interpretable scores diagnose different errors; simulations and wind forecast case study, not tennis. Article CC BY 4.0; R experiment code linked by paper, code license not verified.
- Waghmare & Ziegel (2026), *Proper Scoring Rules for Estimation and Forecast Evaluation*, https://doi.org/10.1146/annurev-statistics-042424-050626 . Review of proper scoring rules; CC BY 4.0; no model performance claim.
Contrary evidence: proper scores on the currently completed subset do not solve selection from unresolved labels. Do not infer outcomes or weight missing records without a defensible mechanism.

## Current evaluation and prioritized next executable queue
- Non-production WTA Web Shadow (unchanged): 104 predictions; 89 settled; 86 completed/scored; 47 correct (54.65%); Brier 0.2513224181; log loss 0.6966212009; 15 pending. Fixed 0.5 baseline Brier 0.25 and log loss ln(2) ~0.693147; shadow worse on both.
- Production immutable champion digest, production qualified-forward denominator, and independently verified latest production settlements were **not** established in this audit; no production performance claim.
1. Download retained source artifact #14022921157 and compare source row MatchID, player IDs, tournament, round, source timestamp, and pre-start evidence for all 15 pending IDs. Include adversarial false-positive controls and no mutation.
2. Independently review 12 plausible legacy source-row candidates and one absent pair; separately investigate 2 exact-ID conflicts. Preserve uncertainty and trust gates.
3. Verify champion digest and qualified forward settlement ledger from main before any prospective paired comparison.
4. Extract immutable common-cohort match-level probabilities and outcomes; preregister chronological paired Brier/log loss and coverage, untouched final holdout, no adaptive tuning.

No production code, predictions, settlements, model promotion, or trust gates changed. No wagering or market inputs.

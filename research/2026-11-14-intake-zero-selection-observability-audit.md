# 2026-11-14 — zero-selection observability audit (research only)

## Hypothesis, baseline and decision
H0: The scheduled WTA intake distinguishes successful source acquisition with zero eligible fixtures from an unsuccessful acquisition in its GitHub Actions job conclusion. Baseline: current `main` at `6b2b6855054fadf3801fd10ea0cf5290a965f067`. Predeclared pass: explicit machine-readable terminal status in the job outputs for zero eligible fixtures, distinguishable from a successful proposal and from an acquisition failure. Failure: zero selection exits successfully without a distinct durable terminal outcome. No model fitting; no final holdout examined.

## Reproducible source evidence
- [Workflow](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/.github/workflows/wta_web_shadow_intake.yml), blob `3e3d3373fbe8df1d8a0f3463560e60ded907bea3`.
- [Intake config](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/intake-config.json), blob `0431001e2cdf48a9742fba931344ac77a975562d`.
- [Intake core](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/scripts/web_shadow_wta_intake_core.py), blob `ee882869f857c403beea793d639f9689d05793a1`.
- [Shadow scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/scorecard.json), blob `c9636ac9d86c256ccf241e652b9456034c451fc3`.

## Executed deterministic experiment
Fetched the three source files from GitHub and ran nine JavaScript assertions on actual file contents: nonproduction flag; four tournament entries; unique year/group identities; 8–48-hour selection window; discovery-only index; explicit `selected=false` and `exit 0` on zero-selection; matching zero-selection error string; always-upload acquisition artifact; and core zero-selection message. **9/9 passed.** Four configured tournament IDs: 1023, 1056, 1074, 1148, all 2026.

The workflow catches `deterministic WTA intake found no eligible unseen matches`, writes `selected=false`, prints a human-readable message and exits 0. The artifact upload step is guarded by `always()` and writes raw source evidence when acquisition was attempted. **H0 is not rejected**: zero eligible fixtures is represented in a step output but the overall workflow can finish green; a distinct durable status field in the artifact was not demonstrated. This is an observability ambiguity, not proof of a source failure. No fresh provider artifact was fetched in this run.

## Scorecard and evidence tier
The current repository WTA Web Shadow (non-production) reports 47/86 accuracy, Brier 0.2513224181, log loss 0.6966212009, 15 pending, 89 settled; Brier exceeds constant 0.25 and log loss exceeds log(2). The production champion's current independently verified qualified-forward denominator was not established. Do not merge or alter receipts or eligibility based on this audit.

## Research, contrary evidence and limitations
- [2026 unified ATP temporal benchmark](https://doi.org/10.3390/analytics5030022): 133,138 men's matches, aligned chronological comparison; enhanced Elo close to more complex alternatives. Published July 3, 2026. External evaluation is ATP rather than WTA; code and trained artifacts are available on request, not independently reproduced here. Do not transfer headline accuracy or market-related inputs.
- [Buhamra et al. 2025](https://doi.org/10.1177/22150218251338954): 5,013 men's Grand Slam matches, expanding and rolling windows; CC BY-NC 4.0; unsuitable for direct performance comparison or unreviewed code reuse. Its chronological protocol is adaptable.
- Contrary possibility: fixing observability alone creates no new fixtures. The expired configured universe and pre-start calculator-state coverage remain separate blockers.

## Next executable queue
1. Inspect retained latest workflow acquisition artifact and verify whether a machine-readable zero-selection outcome exists; if absent, add a narrowly scoped non-production status receipt and regression tests on a separate branch, without weakening gates.
2. Obtain and hash a current official WTA index, validate upcoming event IDs, and compare baseline vs one new verified event in a forward-only dry-run with identical 8–48h gates.
3. Independently verify champion frozen identity and qualified forward settlement receipts; then preregister a single paired probability-calibration challenger on future observations.

No champion, production code, predictions, settlements, or holdout changed.

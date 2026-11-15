# WTA result acquisition static-contract audit — 2026-11-13

**Evidence tier:** read-only workflow/source inspection; no live Actions execution or production forward settlement certified.

## Hypothesis and falsifier
H0: the current main acquisition workflow lacks a guarded, visible zero-selection path and could silently proceed to settlement after no results. Reject H0 only if all ten prespecified source assertions pass. Comparison: explicit fail-closed gate versus unguarded execution; population: main workflow and current WTA shadow scorecard, not an outcome-performance sample.

## Pinned sources
- [workflow](https://github.com/AidanDCM/Tennis-Genome-/blob/main/.github/workflows/wta_web_shadow_results.yml) blob `f49387bb740a664ef5a72ee850203301062dbf2a`
- [scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json) blob `c9636ac9d86c256ccf241e652b9456034c451fc3`
- [active results](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/active-results.json) blob `3bd8dde18bc70f6c411bfc9a56151577b07340e7`
- Existing diagnostic [PR #490](https://github.com/AidanDCM/Tennis-Genome-/pull/490), 12 round discrepancies, one missing pair, two exact-ID conflicts.

## Executed checks
Fetched all three raw GitHub files through the connected GitHub file reader. Ran deterministic JavaScript regex/JSON assertions in the tool runtime:
1. hourly `41 * * * *` schedule: PASS
2. checkout main: PASS
3. visible gate state marker: PASS
4. official-source fetch conditional on successful unblocked gate: PASS
5. zero-result compiler branch emits `selected=false`: PASS
6. settlement path requires `selected=true`: PASS
7. shadow `production_eligible=false`: PASS
8. scored denominator 86: PASS
9. pending denominator 15: PASS
10. one active result path: PASS

**10/10 passed.** Current scorecard: 47/86 correct (54.65%), Brier 0.2513224181341722, log loss 0.6966212008671667. The active-result pointer refers to `web-shadow/results/2026-11-09-chennai-2026-f-ls001-janice-tjen-magda-linette-42775ef387.json`. This is **not** proof that a new result was settled or that a scheduled workflow succeeded. Zero-selection and gate protection are present in source; source-code inspection cannot certify live execution, provenance, or the qualified forward N.

## Research comparison
- [Gneiting & Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437): proper scores evaluate probability quality; no license to treat winner accuracy as calibrated probability evidence.
- [Hersbach (2000), Decomposition of the Continuous Ranked Probability Score for Ensemble Prediction Systems](https://doi.org/10.1175/1520-0434(2000)015%3C0559:DOTCRP%3E2.0.CO;2): adjacent weather verification decomposition motivates separate reliability and resolution reporting; not a tennis result.
- [pytest parametrization documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html): test-case collection may differ from function count; verify exact manifests rather than relying on passing totals.

## Negative results and limitations
H0 rejected at **static-contract level only**. No fresh workflow run logs, independent result identities, pre-start qualified production N, exact-head CI, or live provider source were validated here. No model variation or accuracy gain is claimed. The shadow remains non-production; prior 15 pending matches must not be retrospectively backfilled.

## Next executable queue
1. Inspect newest scheduled WTA acquisition job logs and compiler summary; distinguish gate block, fetch failure, zero selection and proposal.
2. Independently crosswalk 15 pending WTA IDs against retained official source round/player identities without changing any predictions or settlements.
3. Inspect trusted prospective finalizer artifact chain and compute current qualified forward N from verified immutable artifacts.
4. On new chronological qualified predictions only, preregister a fixed shrinkage-to-0.5 challenger versus immutable champion; compare paired Brier/log loss, calibration and coverage, with untouched final holdout and multiple-testing accounting.

No odds, betting inputs, promotion or production modifications.

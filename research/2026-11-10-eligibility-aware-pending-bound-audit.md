# Iteration 31 — eligibility-aware missing-outcome bound and capture audit (2026-11-10)

## Repository provenance and evidence tier
Main SHA from PR #430 base: `8af76720a6291b166263fa1cd8191504f84ed6b6`. Main scorecard `web-shadow/scorecard.json` blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`; active results blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`; main acquisition workflow blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`; forward aggregate workflow blob `1244a36a374d1fb38570ad3f51f0abc9864eab6f`. Connected GitHub open PR search: #428, #429, #430 still open. Main manifest still references the Hong Kong result, not the Chennai proposal. Main acquisition workflow blocks when a result PR is open and checks out main. No change to frozen champion, source or settlement gates.

Main non-production WTA Web Shadow: 88 settled records, 85 scored, 46 correct, Brier 0.2514610585394295, log loss 0.6969082732945988, 16 pending. These are NOT qualified prospective challenger outcomes. Last previously verified forward aggregate reported zero qualified; not freshly verified this iteration.

## Prespecified falsifiable numerical sensitivity experiment
Hypothesis: excluding two known match-ID participant conflicts from the potentially eligible pending denominator narrows the previous all-16 hypothetical winner-accuracy range, but still fails to identify whether full-population accuracy exceeds 50%. Baseline: prior worst-case 46/101 to 62/101 (all 16 potentially eligible). Challenger: only 14 of 16 could qualify under existing identity gates (1 proposed capture, 13 unmatched, 2 identity conflicts). Treat the 14 as a **maximum hypothetical eligible** set, not as settled matches. Success: narrower interval and still straddles 0.5. Failure: assertion fails. No invented winners.

Reproduce (Python 3, no dependencies):
```bash
python - <<'PY'
correct,scored,pending,conflicts=46,85,16,2
assert pending == 1+13+conflicts
old=(correct/(scored+pending),(correct+pending)/(scored+pending))
eligible=pending-conflicts
new=(correct/(scored+eligible),(correct+eligible)/(scored+eligible))
print('old',old,'new',new,'widths',old[1]-old[0],new[1]-new[0])
assert new[0]>old[0] and new[1]<old[1] and new[0]<0.5<new[1]
PY
```
Executed local Python calculations: old 45.5446%–61.3861%; corrected conditional bound **46.4646%–60.6061%**, width 14.1414 pp vs 15.8416 pp. Assertions passed. This is a conditional sensitivity envelope, not a statistical confidence interval. The two identity conflicts are excluded under present evidence, not declared permanently unresolvable. The remaining 14 are not assumed eligible; if fewer qualify, actual population and bounds change.

Second accounting check executed with scipy: among 16 intake predictions, 1 proposed capture (6.25%), 13 unresolved (81.25%), 2 conflicts (12.5%), sum 100%; Jeffreys interval for capture fraction under an *unjustified independent-binomial assumption* ~0.00683–0.25692. This interval is illustrative only and should NOT be treated as an estimate of future capture reliability because observations are not exchangeable and workflow is blocked.

## Operational negative evidence
PR #428 remains open; acquisition gate still prevents fresh snapshots. PR #430 draft receipt code remains unmerged; PR CI is not an end-to-end acquisition execution. One proposed result is not an incorporated settlement. Identity conflicts LS031 and LS020 must remain excluded. No new qualified forward observations established, no model improvement, no CI run executed for this ledger commit.

## Research and contrary evidence
- Kleen (published 2024-04-19), *Scaling and measurement error sensitivity of scoring rules for distribution forecasts*, https://doi.org/10.1002/jae.3056 — theoretical/simulation/economic evaluation, open-access article, economic datasets include restricted proprietary sources; outcome measurement error can change model rankings. No tennis population, code not reused, implementation license not audited.
- Dominitz & Manski (2024-03; revised 2024-05), *Comprehensive OOS Evaluation of Predictive Algorithms with Statistical Decision Theory*, https://www.nber.org/papers/w32269 — working paper, population-shift and target-population uncertainty; no directly comparable tennis performance or code copied.
- Zhao, Ding & Li (2024), *Covariate adjustment in randomized experiments with missing outcomes and covariates*, https://doi.org/10.1093/biomet/asae017 — missing-data weighting results depend on assumptions; randomized experiments, not tennis; not a license to impute unknown match results.

## Highest-value next executable queue
1. Human provenance review of PR #428 and safe disposition; do not bypass immutable proposal gate or automatically merge.
2. Verify PR #430's actual blocked receipt artifact after reviewed main integration; assert no provider fetch, no result mutation and correct SHA/status.
3. Audit the 13 unresolved prediction IDs against source tournament/date/identity coverage, retain raw source hashes and explicit reason categories.
4. Refresh forward aggregate; only when qualified locked observations exist, compare frozen champion against prespecified research-only calibration slope 0.5 with paired Brier/log loss, accuracy, date clusters and untouched holdout.

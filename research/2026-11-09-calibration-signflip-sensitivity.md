# Iteration 6 — exact date-cluster sign-flip sensitivity (2026-11-09)

Evidence tier: exploratory methods research; **no new independent challenger settlements**. Frozen champion and main untouched.

## Audit
Main at `8af76720a6291b166263fa1cd8191504f84ed6b6`. PR #428 remains open (result acquisition; unresolved identities); PR #429 is the research branch. Main Forward Settlement Monitor run 42698460395 was a successful job, but the most recently verified Forward Validation Aggregate 42655914939 reported zero independently settled challenger observations. Non-production Web Shadow scorecard: 88 settled, 85 completed scored, 46/85 winners (54.12%), Brier 0.251461, log loss 0.696908, 16 pending. Research branch exact-head CI 42705658499 succeeded for prior iteration.

## Executed implementation and tests
New `scripts/research_cluster_sign_flip.py` (commit `4981cf49dcf8defe75ca51f7309a54a81b5a59a5`) enumerates every one of 2^G sign configurations for 2 <= G <= 18 date clusters. It computes an exact *conditional sign-flip fraction* for the observed paired mean loss difference, not a validated probability of true superiority. A local copy executed **four deterministic unit checks successfully**: zero differences, equal positive clusters, unequal cluster sizes, invalid inputs. GitHub test file `tests/test_research_cluster_sign_flip.py` committed at `2458fc86ecb7a81066ed1504a78779874efe4f94`; GitHub exact-head CI must be checked separately. This new diagnostic is not yet wired into the existing real-data calibration workflow and no real-data sign-flip result is claimed.

## Research rationale and caveats
MacKinnon, Nielsen & Webb (2023), https://doi.org/10.1002/jae.2969, investigate more reliable cluster-robust bootstrap/jackknife methods when there are few or unbalanced clusters. Gilleland (2020), https://doi.org/10.1175/JTECH-D-20-0069.1, describes bootstrap considerations for comparative forecast verification. Our proposed exact sign-flip method requires cluster sign exchangeability under the sharp null, which is unverified here; date clusters may not be independent, and repeated slope selection on the same paper observations invalidates naive significance interpretations. The 55-match, 15-date-cluster exploratory comparison from iteration 5 had all reported cluster-normal 95% intervals crossing zero. Do not promote any calibration candidate.

## Next executable work
1. Verify exact-head CI for `2458fc86ecb7a81066ed1504a78779874efe4f94`; fix lint or test failures.
2. Integrate sign-flip sensitivity into the existing read-only real-data calibration script, print both adaptive and fixed-half paired Brier/log-loss results, and record exact G and cluster imbalance. Treat results as sensitivity diagnostics only.
3. Resolve PR #428 player identity conflicts without relaxing provenance gates; increase prospective locked challenger settlements and preserve untouched future holdout.
4. After genuinely independent forward evidence, compare predeclared candidate(s) and frozen champion; do not select models from reused exploratory paper outcomes.

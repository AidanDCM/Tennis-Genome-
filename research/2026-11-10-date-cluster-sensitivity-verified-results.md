# Iteration 23 — verified date-cluster sensitivity output (2026-11-10)

**Research-only, no champion/prediction/settlement mutation.** PR #429 head before this documentation commit: `934e1b9b461c4f77a8567772907e08c0b37a8f5d`. GitHub Actions run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42836673187 completed SUCCESS (job 129900604774). Ruff, pytest, and standalone `python scripts/research_calibration_signflip_real.py --repo-root .` steps all succeeded. Complete JSON printed in job log and uploaded as artifact 13773093295 (SHA256 of ZIP `9b25c5c9e37d0188c52cf0a783dcd434cdf9b084b36ac53c5465de6acfd5cb7a`), https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42836673187/artifacts/13773093295 . Script blob `611daf2912a5c7fdb19e9405cccafea487a68e5b`.

## Prespecified hypothesis and observed results

Exactly 55 previously scored WTA Web Shadow observations across 15 UTC match dates, using `evaluation_ids` emitted by the script (first `web:wta:1075:2026:LS007`, last `web:wta:1074:2026:LS001`; full 55 IDs in immutable CI log/artifact). Compare original probabilities with (1) fixed log-odds slope 0.5, (2) chronology-selected adaptive slope. Positive values are baseline minus challenger proper-score loss; leave one date out without refitting.

| Candidate | Full paired Brier improvement | Leave-one-date Brier min..max | Full log-loss improvement | Leave-one-date log-loss min..max | Reversals in 15 exclusions | Exploratory cluster sign-flip fractions Brier/log |
|---|---:|---:|---:|---:|---:|---:|
| Fixed 0.5 | 0.0108904004 | 0.0074632099 .. 0.0160888129 | 0.0238418337 | 0.0154823477 .. 0.0347042005 | 0 | 0.2144775 / 0.2188721 |
| Adaptive | 0.0055672079 | 0.0033736931 .. 0.0084967344 | 0.0123214558 | 0.0067591288 .. 0.0184820586 | 0 | 0.3297119 / 0.3307495 |

For both models, smallest Brier improvement when excluding 2026-11-04, largest when excluding 2026-10-20. Thus the prespecified **single-date influence diagnostic passes**, but the sharp-null sign-flip evidence does **not** establish reliable superiority. Reused retrospective data, 15 clusters, multiple prior looks, and unverified exchangeability prevent promotion or confirmatory significance claims. This is **not** retrained leave-one-cluster-out CV or a prospective challenger test.

## Operational gates

Main active results manifest blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` points to Hong Kong LS001, not unmerged result-acquisition PR #428. PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f` remains open, with snapshot 16 pending inspected, 1 captured finished, 13 unmatched, 2 identity conflicts; do not infer settlements from match ID alone. Main non-production scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb` is not a qualified forward challenger evaluation. Current independently verified forward challenger N not established this run. Champion untouched.

## Independent research and contrary evidence

Decker & Tresp, preprint posted 2026-11-02, https://arxiv.org/abs/2611.03592 : conditional versus pooled calibration can differ in probabilistic time-series models; not tennis-specific, preprint evidence, code/license not verified. Adapt: preregister date/surface/coverage calibration diagnostics on future independent observations, avoiding sparse subgroup claims. Waghmare & Ziegel, published March 2026, https://doi.org/10.1146/annurev-statistics-042424-050626 : proper-score theoretical review, CC BY 4.0, no tennis dataset or directly comparable accuracy. Neither justifies choosing the fixed slope from this reused scorecard.

## Reproduction and queue

Checkout PR #429 at `934e1b9b461c4f77a8567772907e08c0b37a8f5d`; run `ruff check . && pytest -q && python scripts/research_calibration_signflip_real.py --repo-root . > date-cluster-sensitivity.json`. Verify against run artifact, including `evaluation_ids`, 15 exclusions, all 55 matches and fixed/adaptive score ranges.

P0 inspect result-capture workflow freshness, preserve original provider bytes, adjudicate both mismatched identities without weakening gates; prioritize increasing qualified prospective N. P1 collect genuinely new locked champion–challenger pairs with strict pre-start and identity gates, report denominator, Wilson accuracy CI, Brier/log loss, selective coverage, tour/surface/date, drift. P2 only after sufficient prospective N, prespecify simple fixed-vs-original comparison and untouched final holdout. No model promotion or merge.

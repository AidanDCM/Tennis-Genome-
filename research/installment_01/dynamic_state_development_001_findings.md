# DYNAMIC-STATE-DEVELOPMENT-001 — findings

Status: **development comparison complete; default dynamic-state candidate not promoted**

Run date: 2026-09-14

## Reproducible execution

The registered historical comparison completed successfully in GitHub Actions:

- workflow run: `34859180507`
- workflow head: `c9bdb5449129568aed3a919887053436b6ef9b97`
- workflow: `.github/workflows/dynamic_state_real_data_development.yml`
- artifact ID: `10353957388`
- artifact SHA-256: `dbed32ffa8e7f555c7591b217d72799d998104f2f02d34d260ab3fe3e87cdbfe`
- pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- development source coverage: 2000–2025
- scored test years: 2015–2025
- evidence role: **DEVELOPMENT_ONLY**

The workflow rebuilt the canonical ATP/WTA source from the pinned archive and failed closed unless the previously archived canonical hashes reproduced exactly.

### ATP canonical reproduction

- rows: `77,850`
- source bundle SHA-256: `b5cf078bb2bc035bb3a2c3bdc7d70b2eeabf38957ce5a2614f5d129c8484627c`
- pre-match SHA-256: `d1003f47322a58ff92ec1dc98d68168c136a7423a58cfd8e9f43530a6b252442`
- outcome SHA-256: `9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0`
- stats SHA-256: `56b542915523a5e78bf7eedf91b6fbfea5a83f0a10498496bd4689747e08c0d9`

### WTA canonical reproduction

- rows: `71,419`
- source bundle SHA-256: `b98b0b28e447eb13e2352b3d555be96d39d7dd4e49121fa84eaf87b9465a3fc2`
- pre-match SHA-256: `16c1b6ff231c10169142a6e038d035d56c082f843fe509084eda5436d4b39262`
- outcome SHA-256: `1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8`
- stats SHA-256: `db75fe1b22ab48c64e024a5acadc44ec1b18f536516ef7fb02f806c672bf1df1`

## Registered comparison

Both forecasting procedures used the same match-win model and exactly the same legal inputs:

- overall prior-date Elo logit;
- opponent-adjusted serve/return matchup edge;
- the existing frozen `FeatureProbabilityModel` pipeline.

The only difference was the serve/return state estimator:

1. existing fixed-learning-rate state;
2. uncertainty-aware dynamic state from the prior known-truth benchmark.

Dynamic uncertainty itself was **not** supplied as a predictor.

Target-row ranking, age, surface, seed, round and other currently unresolved v2 target context were excluded.

Positive deltas below mean lower loss for the dynamic candidate.

## Results

| Tour | N | Fixed Brier | Dynamic Brier | Δ Brier | 95% block CI | p | Fixed log loss | Dynamic log loss | Δ log loss | 95% block CI | p |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---:|
| ATP | 29,587 | 0.21163201 | 0.21312529 | **-0.00149328** | [-0.00186734, -0.00112549] | 0.000050 | 0.61014185 | 0.61347422 | **-0.00333237** | [-0.00416658, -0.00248268] | 0.000050 |
| WTA | 27,664 | 0.21821160 | 0.21807487 | **+0.00013672** | [-0.00003094, +0.00030685] | 0.121544 | 0.62549829 | 0.62510418 | **+0.00039411** | [+0.00002331, +0.00077151] | 0.044048 |

Calendar-week blocks were preregistered before the result. The reported intervals are paired block-bootstrap intervals; p-values are paired block sign-flip tests.

## Provenance identities

### ATP

- stable source-manifest identity: `742283031b9a89f703ae852511ef207e16dde7b70f961d02db102e785aa060a8`
- availability registry: `b25061c719c8589c9c087c335d4e76e245856a84a2fcdd5ad558d8c072d5da18`
- dataset fingerprint: `df3822aa1129ba825de9300cf74f5b948171309e02bbaa3e6fabf8d813fe58cf`

### WTA

- stable source-manifest identity: `9d43d556933947879d61c51a83865a8ee48a885df45b141e588136dd5c6d42d2`
- availability registry: `36dea81b8d15ecb99acf448c732779c58072b828c207cbcad7525ed7715dcbdc`
- dataset fingerprint: `b97a5d9fef5916e836d3ef4722d26c5c43c829d24c17d5d0d701106d150bd2ea`

Shared code fingerprint:

`bc31f1d7f2831adc007732a4ff4cf6343b309138ece3165dd1420fad53020449`

## Interpretation

### ATP

The default dynamic-state candidate is **rejected as a replacement** for the existing fixed serve/return state.

The degradation is not a tiny ambiguous fluctuation:

- both proper scores worsen;
- both dependence-aware intervals are entirely on the wrong side of zero;
- both block sign-flip tests strongly reject a zero-centered difference.

The known-truth shift benchmark therefore demonstrated mechanism capability, not real ATP forecasting superiority. The likely explanations include overreaction, excessive mean reversion/process variance, mismatch between the synthetic shift world and real player evolution, or noisy/incomplete historical point-stat observations.

This negative evidence must remain part of the research history.

### WTA

WTA is **not promoted** either.

The candidate shows:

- a very small favorable Brier point estimate whose interval crosses zero;
- a very small favorable log-loss result whose interval is just above zero.

That is a narrow clue that the dynamic state may behave differently by tour, not evidence that the complete procedure is superior.

A follow-up must not be described as confirmation of this result, and parameter tuning on the same exposed history must be registered as a search family with all attempted variants counted.

## Decision

1. Do **not** replace the existing fixed serve/return state in TGE-Independent-v1.
2. Do **not** open protected evidence for this candidate.
3. Do **not** infer market edge or profitability.
4. Preserve ATP as negative evidence against this exact dynamic parameterization.
5. Treat WTA as a hypothesis-generation signal only.
6. Before any dynamic-state parameter search, register the complete bounded search family and its multiplicity.
7. The most useful next diagnostic is to decompose why ATP worsens — especially layoff length, prior-history depth, missing-stat coverage and uncertainty magnitude — without selecting a new winner post hoc.

No frozen prospective protocol or prospective N changed in this experiment.

# DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001

Status: **preregistered historical development search; candidate outcomes unopened**

## Motivation

`DYNAMIC-STATE-DEVELOPMENT-001` rejected the original uncertainty-aware dynamic serve/return parameterization on ATP and showed only a small mixed WTA result.

`DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001` then showed, descriptively, that the ATP damage was amplified by sparse/extreme information states but remained negative even in ordinary-layoff, deep-history and low-uncertainty rows. WTA gains were concentrated in ordinary, moderately uncertain states and reversed in sparse/extreme states.

The next experiment therefore asks a narrow mechanistic question:

> Can a **less aggressive** dynamic state preserve useful adaptation without the broad ATP penalty of the failed parent parameterization?

This protocol freezes the entire candidate universe before any candidate result is inspected.

## Parent parameterization

The failed parent dynamic configuration was:

- base service win rate: `0.62`
- initial variance: `0.50`
- process variance per day: `0.001`
- mean-reversion half-life: `365` days
- point-information weight: `0.10`
- minimum variance: `0.02`
- maximum variance: `1.50`

The fixed serve/return comparator remains unchanged:

- base service win rate: `0.62`
- learning rate: `0.50`
- reference points: `60`

## Frozen candidate family

Exactly three dynamic-state axes may vary:

1. process variance per day: `{0.00025, 0.00050}`
2. mean-reversion half-life: `{730, 1460}` days
3. maximum variance: `{0.75, 1.00}`

The complete Cartesian product is evaluated: **2 × 2 × 2 = 8 candidates**.

All other dynamic parameters remain frozen at the parent values:

- base service win rate `0.62`
- initial variance `0.50`
- point-information weight `0.10`
- minimum variance `0.02`

Every candidate is less aggressive than the failed parent on all three varied axes: lower daily process variance, slower mean reversion, and a lower variance ceiling.

### Registered candidate IDs

- `DYN-LA-PV00025-HL730-MV075`
- `DYN-LA-PV00025-HL730-MV100`
- `DYN-LA-PV00025-HL1460-MV075`
- `DYN-LA-PV00025-HL1460-MV100`
- `DYN-LA-PV00050-HL730-MV075`
- `DYN-LA-PV00050-HL730-MV100`
- `DYN-LA-PV00050-HL1460-MV075`
- `DYN-LA-PV00050-HL1460-MV100`

No ninth candidate may be added after results are opened. A materially different parameterization requires a new registered family and counts as a new research exposure.

## Data and chronology

Use the same pinned historical research source as the parent experiment:

`Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`

Development source coverage: **2000–2025**.

Evaluate both ATP and WTA.

Target test years: **2015–2025**.

For every test year `Y`, fit the match-win mapping only on rows from years `< Y`.

Minimum training rows: `5,000`.

Walkovers and retirements remain excluded under the parent convention.

Historical source chronology remains date-only with the conservative same-day freeze. No intraday order is invented.

## Forecasting procedure

Every candidate uses exactly the parent match-win pipeline:

- prior-date overall Elo logit;
- one opponent-adjusted serve/return matchup edge;
- the existing `FeatureProbabilityModel` logistic mapping.

The only difference across the eight candidates is the three registered dynamic-state parameters above.

Dynamic uncertainty is not supplied as a match-win predictor.

No target-row rank, surface, seed, age, round, odds, market information, or other unresolved v2 context enters this search.

## Primary metrics and dependence-aware inference

Primary metrics:

1. Brier score
2. log loss

Positive `fixed - candidate` deltas mean lower loss for the dynamic candidate.

Use the parent dependence treatment:

- block definition: ISO calendar week
- confidence level: 95%
- paired block bootstrap resamples: 10,000
- paired block sign-flip resamples: 20,000
- inference seed: `20260914`

## Search multiplicity

The candidate family has:

- 8 registered procedures
- 2 tours
- 2 primary metrics

Therefore there are **32 primary historical claims**.

Familywise alpha is `0.05`.

For any claim of familywise statistically supported historical improvement, use the conservative Bonferroni threshold:

`0.05 / 32 = 0.0015625`

Raw intervals and raw p-values may still be reported, but they must not be described as familywise significant unless they satisfy the registered multiplicity threshold.

## Frozen candidate-selection rule

Candidate selection for a possible *next-stage development candidate* is separated from inferential language.

A candidate is eligible for selection only if its aggregate point estimate is favorable in **all four tour × metric cells**:

- ATP Brier improvement > 0
- ATP log-loss improvement > 0
- WTA Brier improvement > 0
- WTA log-loss improvement > 0

If no candidate passes all four sign gates, the family returns **NO CANDIDATE**.

If one or more candidates pass all four gates:

1. pool ATP and WTA prediction rows and choose the candidate with the largest pooled mean log-loss improvement;
2. if tied, choose the largest pooled mean Brier improvement;
3. if still tied, choose lexicographically smallest candidate ID.

This selection rule is historical-development model selection only. It does not establish protected, prospective, or market superiority.

## Interpretation rules

Allowed:

- compare all eight registered candidates;
- report every tour × metric result;
- identify whether any candidate passes the frozen four-cell sign gate;
- report the preregistered selected development candidate if one exists;
- report which claims, if any, satisfy the 32-claim Bonferroni threshold.

Not allowed:

- adding a ninth candidate after seeing results;
- changing a parameter value because a neighboring candidate looked promising;
- selecting separate ATP and WTA winners under this family;
- selecting a favorable layoff, history-depth, or uncertainty subgroup;
- changing the four-cell sign gate after results are known;
- opening protected evidence because a historical candidate looks good;
- claiming market edge or profitability;
- changing prospective N.

## Evidence status

All results are `DEVELOPMENT_SEARCH_ONLY`.

A selected candidate, if any, is merely eligible for separately preregistered follow-up. It does not alter TGE-Independent-v1 or any frozen prospective protocol.

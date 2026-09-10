# PROFILE-GAP-001 — Findings

Status: **historical development result; not independently forward-confirmed**

This document records the result of the preregistered experiment in `profile_gap_protocol.md` plus `profile_gap_preresult_amendment_001.md`. The promotion rules are applied as written. No year, subgroup, feature, or threshold is removed after seeing the result.

## Accepted run

- Workflow: `Player Profile Gap Research`
- Run ID: `34427178193`
- Research head: `4b6631d548dd563fab7802150c247bc62d56348d`
- Artifact: `tennis-genome-profile-gap`
- Artifact ID: `10133269797`
- Artifact digest: `sha256:a1444c788796afb45696c7acd63fbdf93125c759a0d8550daa50c952842ccf94`
- Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Historical source coverage: 2000–2025 only
- Partial-2026 holdout: explicitly excluded and already considered spent from prior milestones
- Primary convention: walkovers and retirements excluded
- Minimum outer-year training population: 1,000 matches

All three registered executions completed successfully before result interpretation:
1. ATP strict Profile Strength;
2. WTA strict Profile Strength;
3. WTA conditional serve/return diagnostic.

The experiment code independently rejects selected-tour rows after 2025 in addition to the workflow guard.

## Result summary

| Representation | N | Elo Brier | Profile Brier | Δ Brier vs Elo | Elo log loss | Profile log loss | Δ log loss vs Elo | Elo accuracy | Profile accuracy | Strict Core Brier | Strict Core log loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ATP strict | 71,832 | 0.211137 | 0.206619 | **+0.004518** | 0.609367 | 0.598730 | **+0.010637** | 66.21% | **67.20%** | 0.204713 | 0.594175 |
| WTA strict | 66,224 | 0.211338 | 0.210163 | **+0.001175** | 0.609344 | 0.609777 | **−0.000433** | 66.13% | **66.81%** | 0.206065 | 0.598090 |
| WTA conditional serve/return | 66,224 | 0.211338 | 0.210171 | **+0.001168** | 0.609344 | 0.610357 | **−0.001013** | 66.13% | **66.85%** | 0.206065 | 0.598090 |

Positive Δ Brier/log loss means Profile Strength is better than Elo.

## ATP strict: passes the frozen historical-development gate

ATP strict satisfies every registered Profile Strength development criterion:

- aggregate Brier improves by `+0.004518`;
- aggregate log loss improves by `+0.010637`;
- accuracy improves by about `+0.99 percentage points`;
- ECE-10 improves from `0.022390` to `0.011345`;
- Profile Strength beats Elo on **both Brier and log loss in 25/25 evaluated years**;
- 2021–2025 aggregate Brier and log loss both improve;
- player-order symmetry, same-date freeze, future-append invariance, and representation-equivalence tests pass in CI.

Recent 2021–2025 block, N = 14,158:

- Elo Brier `0.218698` → Profile `0.213220` (`+0.005479`);
- Elo log loss `0.626742` → Profile `0.613793` (`+0.012948`);
- Elo accuracy `64.10%` → Profile `65.37%` (`+1.27 pp`).

The improvement is not isolated to low-history players. Registered minimum-prior-match slices remain positive through `>=50` prior matches, and point-history slices remain positive through `>=1000` points. Complete and incomplete 14-day duration-coverage groups are also both positive versus Elo.

### ATP interpretation

**Decision:** ATP Profile Strength v1 survives as a development candidate for intrinsic player-state strength.

It does **not** replace strict Core v1. Strict Core remains better:

- Core Brier `0.204713` vs Profile `0.206619`;
- Core log loss `0.594175` vs Profile `0.598730`;
- Core accuracy `67.67%` vs Profile `67.20%`.

That is consistent with the architecture: Player Profile intentionally excludes match-environment/context families that belong to the matchup layer. Profile Strength is a player-state coordinate and Genome substrate, not the complete match predictor.

## ATP Profile Gap: provisional historical support for H-009

The registered Profile Gap direction is strongly present out of sample.

Aggregate:

- residual slope of Elo residual on Profile Gap: **`+0.163667`**;
- Q5 minus Q1 mean Elo residual: **`+0.180596`**.

Recent 2021–2025:

- residual slope: **`+0.180227`**;
- Q5 minus Q1 Elo residual: **`+0.189005`**.

Full-history gap quintiles:

| Gap quintile | Mean Profile Gap | Mean Elo p(A) | Realized A win rate | Mean Elo residual |
|---:|---:|---:|---:|---:|
| Q1 | −0.5959 | 61.19% | 50.55% | −0.1064 |
| Q2 | −0.2556 | 54.54% | 49.35% | −0.0519 |
| Q3 | −0.0701 | 51.29% | 50.38% | −0.0091 |
| Q4 | +0.1114 | 47.85% | 50.37% | +0.0251 |
| Q5 | +0.4371 | 41.60% | 49.02% | +0.0742 |

This is the expected H-009 pattern: when Profile Strength says A is stronger relative to Elo, A subsequently beats Elo expectation more often; when Profile Strength says A is weaker, A underperforms Elo expectation.

**Decision:** H-009 receives **provisional historical support for ATP**. Profile Gap becomes a frozen candidate trajectory/uncertainty signal for genuinely future confirmation and for the Tennis Genome neighborhood experiment.

It is not a betting edge and no Profile Gap threshold is promoted.

## WTA strict: fails the frozen promotion gate

WTA strict is interesting but does **not** survive the registered Profile Strength promotion gate.

Positive evidence:

- Brier improves by `+0.001175` aggregate;
- accuracy improves by about `+0.68 pp`;
- joint Brier + log-loss wins occur in 23/25 evaluated years;
- 2021–2025 Brier and log loss both improve materially;
- Profile Gap has the registered positive aggregate and recent direction.

But the protocol requires aggregate Brier **and aggregate log loss** to improve. Aggregate log loss is worse:

- Elo `0.609344`;
- WTA strict Profile `0.609777`;
- Δ log loss `−0.000433`.

Therefore the gate fails exactly as preregistered.

### WTA 2016 adversarial diagnostic

The aggregate failure is dominated by a severe 2016 instability, but **2016 is retained**.

2016 strict WTA:

- N `2,836`;
- Elo Brier `0.221004` vs Profile `0.249017`;
- Elo log loss `0.632365` vs Profile `0.769126`;
- Elo accuracy `64.39%` vs Profile `63.50%`;
- 18.0% of Profile predictions are below 5% or above 95%, compared with 0.8% in 2015 and about 0.1% in 2017.

A source-coverage regime shift is visible in the registered duration-quality descriptor:

- 2015: about **20.9%** of WTA target rows have complete 14-day duration history for both players;
- 2016: about **94.0%**;
- 2017: about **97.0%**.

The abrupt appearance of workload-duration information at the same time as extreme confidence is a plausible covariate-shift mechanism. It is **not proven to be the sole cause** from the accepted artifact, and no coefficient, clipping, feature removal, year exclusion, or threshold change is introduced after seeing the result.

The model immediately returns to positive Brier/log-loss deltas in 2017 and every year through 2025, which strengthens the diagnosis of a one-time representation/data-regime transition but does not erase the failed aggregate gate.

### WTA interpretation

**Decision:** WTA strict Profile Strength remains experimental; it is not promoted from PROFILE-GAP-001.

Because the preregistered protocol says Profile Gap cannot be promoted when Profile Strength itself fails the Elo gate, H-009 does **not** receive formal WTA promotion from this experiment, despite the positive gap diagnostics.

The WTA result is useful evidence for a future explicitly preregistered covariate-shift/OOD treatment. It is not permission to retrospectively repair this experiment.

## WTA conditional serve/return diagnostic

Adding the already B/Conditional WTA serve/return state does not rescue the strict result.

Aggregate:

- Brier improvement vs Elo: `+0.001168`;
- log-loss improvement vs Elo: **`−0.001013`**;
- accuracy improvement: about `+0.72 pp`;
- joint year wins: 23/25.

2016 becomes slightly worse than WTA strict:

- Profile Brier `0.251478`;
- Profile log loss `0.784433`.

Recent 2021–2025 is good, but this experiment does not permit a recent-only promotion.

**Decision:** WTA serve/return remains **B/Conditional**. PROFILE-GAP-001 provides no reason to upgrade it to WTA Core.

## What the experiment established

1. A mathematically symmetric, player-side Profile Strength coordinate can be learned chronologically without hand-set weights.
2. ATP Profile Strength contains stable incremental historical predictive information beyond overall Elo across every evaluated year in this development sample.
3. ATP Profile Gap strongly orders subsequent Elo residuals in the registered direction.
4. The intrinsic profile representation still underperforms the full strict Core match model, supporting the intended separation between player state and match context.
5. WTA exposes a major representation/data-regime sensitivity in 2016; the failure is preserved rather than optimized away.
6. The source-depth and duration-quality descriptors are useful for diagnosing uncertainty/OOD behavior without being smuggled into Profile Strength.

## What the experiment did not establish

- no sportsbook odds were used;
- no EV, CLV, ROI, staking, or betting profitability was tested;
- no Profile Gap threshold was tested or promoted as a wager/PASS rule;
- no causal interpretation is justified;
- no new untouched future holdout exists;
- the current CC BY-NC-SA source is research-only and not a production-data solution;
- WTA Profile Strength has not passed the frozen promotion gate;
- ATP historical success is not independent forward confirmation.

## Frozen decisions for the next milestone

### ATP
- preserve Player Profile v1 as the player-state representation;
- preserve strict ATP Profile Strength as a **development candidate**;
- preserve ATP Profile Gap as a **provisionally supported historical trajectory signal**;
- do not tune a gap threshold from this result;
- use Profile v1 + match context as inputs to the Tennis Genome historical-neighborhood experiment.

### WTA
- preserve the same Profile v1 storage representation;
- do not promote strict Profile Strength;
- do not promote Profile Gap from this experiment;
- keep serve/return B/Conditional;
- carry an explicit OOD/data-regime diagnostic into the Genome work rather than deleting the 2016 failure.

## Next experiment

Proceed to the preregistered Tennis Genome / historical-neighborhood residual program:

- H-011 historical-neighborhood similarity;
- H-012 residual-neighborhood correction;
- H-013 density/OOD diagnostics.

Similarity must use structured mathematical state, strict historical neighbors only, training-fitted transforms only, and residual prediction relative to the frozen baseline. Rendered fingerprint/waveform images remain visualization only and must never define similarity.

# Research Baseline Findings 002 — EXP-003 Opponent-Adjusted Serve/Return

Status: **accepted research result**

Experiment: **EXP-003 — Elo + Opponent-Adjusted Serve/Return**

Accepted research run:
- GitHub Actions run: `34412341381`
- branch head: `fe7c96f017acd0a6c5c2266974e7bde17e43e3e0`
- artifact ID: `10127818943`
- artifact SHA-256: `69f96e1fbadd05ecad8279406a2fdffea0d0f6b66c0332f00de8416af7a99dc9`
- source archive: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- coverage: ATP/WTA tour-level singles, 2000–2025
- source permission: research-only, CC BY-NC-SA 4.0

The EXP-003 research contract and interpretation rules were committed before the accepted run completed. This document records the result; it does not rewrite the registered hypothesis.

---

## Decision

### ATP: A / Core candidate

Opponent-adjusted serve/return is promoted into the ATP core research stack.

Reasons:
- aggregate Brier and log loss both improve,
- Brier improves in **25/25** evaluated seasons,
- log loss improves in **25/25** evaluated seasons,
- the effect becomes larger in the `250+` and `1000+` prior-point slices rather than disappearing,
- the same direction survives the fixed chronological evaluation and target-stat leakage controls.

This is unusually stable for a first feature-family experiment. It does not prove optimal parameterization, betting profitability, or causal interpretation.

### WTA: B / Conditional / low-weight candidate

Opponent-adjusted serve/return is retained for WTA, but not promoted with ATP-equivalent weight.

Reasons:
- aggregate Brier and log loss are positive,
- the mature-history slices improve more than the full population,
- Brier improves in **20/25** evaluated seasons,
- log loss improves in **17/25** evaluated seasons,
- the absolute effect is materially smaller than ATP,
- calibration ECE does not improve in the aggregate WTA result.

The WTA signal becomes more consistent in later seasons: every season from 2016 through 2025 has positive Brier improvement, and every season from 2019 through 2025 has positive Brier and log-loss improvement. This is a diagnostic observation, not permission to redefine the registered population after seeing the result.

---

## Accepted configuration

EXP-003 v1 was frozen before the final result:

- base service-point win probability: `0.62`
- learning rate: `0.50`
- reference points: `60`
- update weight: `min(service_points / 60, 1)`
- residual split equally between server serve strength and receiver return strength
- same canonical date frozen before updates
- walkovers excluded
- primary view excludes retirements
- baseline: chronologically calibrated Elo
- challenger: chronologically calibrated Elo + serve/return matchup edge
- `StandardScaler` fitted on prior-year training data only
- logistic regression fitted separately inside each historical training fold
- minimum historical training population: `1000` matches

No parameter search was performed after observing the result.

---

## ATP result

Population: **71,832** future predictions.

| Metric | Calibrated Elo | Elo + Serve/Return | Change |
|---|---:|---:|---:|
| Brier | 0.210424 | 0.208790 | **+0.001634 improvement** |
| Log loss | 0.607185 | 0.603402 | **+0.003783 improvement** |
| Accuracy | 66.1293% | 66.2671% | **+0.1378 pp** |
| ECE-10 | 0.010366 | 0.011649 | -0.001282 deterioration |

Accuracy is secondary. The central result is the stable improvement in both proper probability scores.

### ATP historical-depth slices

| Minimum prior points on every required side | N | Brier improvement | Log-loss improvement | Accuracy change |
|---|---:|---:|---:|---:|
| 0+ | 71,832 | +0.001634 | +0.003783 | +0.1378 pp |
| 250+ | 63,612 | **+0.002086** | **+0.004728** | +0.4323 pp |
| 1000+ | 57,019 | **+0.002016** | **+0.004536** | +0.4104 pp |

The mature-history slices strengthen the result. Cold start therefore suppresses part of the available signal rather than manufacturing the aggregate gain.

In the `250+` and `1000+` ATP slices, ECE also improves relative to the paired calibrated-Elo baseline, despite the aggregate ECE deterioration.

### ATP temporal stability

- Brier improvement: **25/25** evaluated seasons.
- Log-loss improvement: **25/25** evaluated seasons.
- Accuracy improvement: 15/25 seasons.

The proper-score result is therefore substantially more stable than the secondary winner-classification result.

---

## WTA result

Population: **66,224** future predictions.

| Metric | Calibrated Elo | Elo + Serve/Return | Change |
|---|---:|---:|---:|
| Brier | 0.210929 | 0.210685 | **+0.000244 improvement** |
| Log loss | 0.608930 | 0.608530 | **+0.000400 improvement** |
| Accuracy | 66.6148% | 66.7190% | **+0.1042 pp** |
| ECE-10 | 0.026770 | 0.027584 | -0.000814 deterioration |

The direction is favorable, but the effect is much smaller than ATP and does not justify ATP-equivalent confidence.

### WTA historical-depth slices

| Minimum prior points on every required side | N | Brier improvement | Log-loss improvement | Accuracy change |
|---|---:|---:|---:|---:|
| 0+ | 66,224 | +0.000244 | +0.000400 | +0.1042 pp |
| 250+ | 46,370 | +0.000322 | +0.000515 | +0.1574 pp |
| 1000+ | 37,389 | **+0.000345** | **+0.000625** | +0.1364 pp |

The effect strengthens as the minimum historical point exposure rises. That supports treating data maturity as relevant to WTA confidence rather than discarding the feature family entirely.

### WTA temporal stability

- Brier improvement: **20/25** evaluated seasons.
- Log-loss improvement: **17/25** evaluated seasons.
- Accuracy improvement: 17/25 seasons.
- 2001–2003 show effectively zero incremental signal under this v1 state.
- 2008 and 2015 show small negative Brier changes.
- every season from 2016–2025 has positive Brier change.
- every season from 2019–2025 has positive Brier and log-loss change.

These later-period diagnostics should motivate source-coverage and model-specification research, not post-hoc deletion of earlier seasons.

---

## Canonical-v2 provenance

### ATP

- canonical rows: `77,850`
- date range: `2000-01-03` through `2025-12-17`
- source files: `26`
- source bundle SHA-256: `b5cf078bb2bc035bb3a2c3bdc7d70b2eeabf38957ce5a2614f5d129c8484627c`
- pre-match SHA-256: `207c4c989cb943c6a7c5894ccc59d984cdacbef3b4ca88ba99155efd05e2e700`
- outcome SHA-256: `9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0`
- stats SHA-256: `468eaded79161557dc011b61cda56818f41ffe0cc772cd0b6e384f46f6de1d05`
- quality warnings: 53 unknown-surface rows

### WTA

- canonical rows: `71,419`
- date range: `2000-01-03` through `2025-11-01`
- source files: `26`
- source bundle SHA-256: `b98b0b28e447eb13e2352b3d555be96d39d7dd4e49121fa84eaf87b9465a3fc2`
- pre-match SHA-256: `cbd7ba75ee8d86516f087bcced6a6e222721a8bc8c115448b6c1d8c2116ee0bf`
- outcome SHA-256: `1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8`
- stats SHA-256: `90228cc76d57e9bcd7ed88c5e693c1004163037140e101cb9a5240da11eb449c`
- quality warnings: 113 unknown-surface rows

EXP-001 and EXP-002 both reproduced successfully after the canonical-v2 upgrade, providing a regression check that adding the physically separate stats artifact did not change the earlier baseline conclusions.

---

## What EXP-003 establishes

The result supports a specific claim:

> Historical service-point performance contains incremental pre-match information beyond overall Elo when it is transformed into a date-frozen, opponent-adjusted serve/return state.

That claim is strongest for ATP. For WTA it is smaller and should remain conditional/low-weight until deeper work explains the tour difference.

The result does **not** establish:
- betting profitability,
- an edge over sportsbook prices,
- optimal serve/return parameters,
- causal player traits,
- exact-match-day updating when only tournament-start-era dates are available,
- that every serve statistic should be added to the model,
- that calibration is solved.

---

## Important timing limitation

The source `tourney_date` is generally tournament-start-era timing, often the Monday of the tournament week, rather than a trustworthy exact match start timestamp.

The same-date freeze is therefore deliberately conservative: multiple matches from the same event can share a frozen pre-event state even when real-world chronology would have allowed an earlier round to inform a later round. This sacrifices some potentially valid information to prevent CSV row order from creating synthetic chronology.

A future source with trustworthy match timestamps can test whether exact chronological updates increase signal without leakage.

---

## Next registered directions

1. **EXP-004 Recent Form** — proceed with the next planned independent information family while keeping Elo + ATP serve/return as the stronger benchmark stack.
2. **Serve/return source coverage audit** — quantify valid point-stat availability by tour and season, especially to explain WTA's smaller early-period signal.
3. **Serve/return v2 hypotheses, separately registered** — possible recency decay, surface conditioning, hierarchical shrinkage, first/second-serve decomposition, and break-point-derived features. None may be retroactively called part of EXP-003 v1.
4. **Calibration layer research** — proper scores improve, but aggregate ECE does not improve on either tour under v1; calibration remains a separate objective.

The architecture rule remains unchanged: a feature family earns complexity only by surviving unseen chronological data.
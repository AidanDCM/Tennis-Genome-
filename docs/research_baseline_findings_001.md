# Research Baseline Findings 001 — Ranking, Elo, and Surface Elo

Status: **research finding; not production or betting-edge evidence**

## Snapshot

These findings come from Research Snapshot 001:

- ATP and WTA tour-level singles
- completed seasons 2000–2025
- pinned archival source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- source license: CC BY-NC-SA 4.0 / research-only for Tennis Genome
- primary views exclude walkovers and retirements
- exact same-day match order is not inferred

The source's repeated ranking fields are documented as the ATP/WTA ranking on `tourney_date`, or the most recent ranking date before it. `tourney_date` is usually the Monday of the tournament week.

During the first WTA build, the integrity gate identified reused source `match_num` values in the 2009 Tournament of Champions. Source inspection showed that these were distinct matches in different rounds rather than duplicate records. The adapter was changed so only colliding base IDs receive a deterministic suffix derived from pre-match-safe round and canonical player-pair identity. Exact duplicate records still collide and remain fatal.

---

## Canonical provenance

### ATP

- raw rows: **77,850**
- canonical date range: `2000-01-03` through `2025-12-17`
- source files: **26**
- source bundle SHA-256: `b5cf078bb2bc035bb3a2c3bdc7d70b2eeabf38957ce5a2614f5d129c8484627c`
- pre-match Parquet SHA-256: `207c4c989cb943c6a7c5894ccc59d984cdacbef3b4ca88ba99155efd05e2e700`
- outcome Parquet SHA-256: `9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0`
- quality warnings: 53 unknown-surface rows

### WTA

- raw rows: **71,419**
- canonical date range: `2000-01-03` through `2025-11-01`
- source files: **26**
- source bundle SHA-256: `b98b0b28e447eb13e2352b3d555be96d39d7dd4e49121fa84eaf87b9465a3fc2`
- pre-match Parquet SHA-256: `cbd7ba75ee8d86516f087bcced6a6e222721a8bc8c115448b6c1d8c2116ee0bf`
- outcome Parquet SHA-256: `1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8`
- quality warnings: 113 unknown-surface rows

Unknown surfaces remain explicit rather than being guessed. EXP-002 excludes them from both models and their training stream.

---

# EXP-001 — Ranking vs overall Elo

## ATP

Common evaluation population: **70,200 matches**.

| Metric | Ranking | Elo | Elo change |
|---|---:|---:|---:|
| Accuracy | 65.9630% | 66.2821% | **+0.3191 pp** |
| Brier | 0.212511 | 0.210781 | **-0.001730** |
| Log loss | 0.612580 | 0.608594 | **-0.003985** |
| 10-bin ECE | 0.008306 | 0.025128 | **worse by 0.016822** |

Relative to ranking, the Elo Brier reduction is about **0.81%** and the log-loss reduction about **0.65%**.

Year stability:

- Elo has lower Brier in **19 of 25** evaluated years.
- Elo has lower log loss in **17 of 25** years.
- Elo has higher accuracy in 16 years, lower accuracy in 8, and ties once.
- The last ten evaluated seasons still favor Elo on average, but the probability-quality improvement is smaller than across the full history.

Decision: **promote overall Elo as an A/Core baseline candidate for ATP**, while retaining ranking as an external baseline and disagreement signal.

## WTA

Common evaluation population: **63,055 matches**.

| Metric | Ranking | Elo | Elo change |
|---|---:|---:|---:|
| Accuracy | 65.8663% | 66.3326% | **+0.4663 pp** |
| Brier | 0.213591 | 0.210177 | **-0.003413** |
| Log loss | 0.615375 | 0.606758 | **-0.008616** |
| 10-bin ECE | 0.014891 | 0.022139 | **worse by 0.007248** |

Relative to ranking, the Elo Brier reduction is about **1.60%** and the log-loss reduction about **1.40%**.

Year stability:

- Elo has lower Brier in **23 of 25** evaluated years.
- Elo has lower log loss in **21 of 25** years.
- Elo has higher accuracy in 17 years, lower accuracy in 7, and ties once.
- The last ten evaluated seasons continue to show a clear average Elo advantage.

Decision: **promote overall Elo as an A/Core baseline candidate for WTA**.

## Calibration caveat

Raw starter Elo improves Brier and log loss on both tours despite having worse fixed-bin ECE than the calibrated ranking-logit model.

This means the project should not interpret EXP-001 as evidence that the starter Elo probabilities are fully calibrated. It is evidence that Elo carries stronger probability information overall. Chronological probability calibration remains a registered follow-up, not a retroactive change to EXP-001.

---

# EXP-002 — Overall Elo vs pure Surface Elo

Surface Elo v1 gives each player fully independent Hard, Clay, Grass, and Carpet ratings. It does not share information with overall Elo or between surfaces.

## ATP

Common known-surface population: **75,060 matches**.

| Metric | Overall Elo | Surface Elo | Surface change |
|---|---:|---:|---:|
| Accuracy | 66.0139% | 65.1625% | **-0.8513 pp** |
| Brier | 0.211996 | 0.214181 | **+0.002185 worse** |
| Log loss | 0.611295 | 0.615901 | **+0.004607 worse** |
| 10-bin ECE | 0.020504 | 0.020420 | roughly unchanged |

Year stability:

- Surface Elo has better Brier in only **3 of 26** years.
- It has worse Brier in 23 years.
- It has worse log loss in 22 of 26 years.
- It has worse accuracy in 22 of 26 years.

By surface:

- **Clay:** Surface Elo is modestly better on Brier (`+0.000865` improvement) and log loss (`+0.002274` improvement), while accuracy is about 0.19 pp lower.
- **Hard:** Surface Elo is worse.
- **Grass:** Surface Elo is materially worse.
- **Carpet:** Surface Elo is substantially worse.

By weaker-player prior surface experience:

- 0 matches: Surface Elo Brier disadvantage ≈ `0.010043`.
- 1–4: disadvantage ≈ `0.004601`.
- 5–9: disadvantage ≈ `0.002025`.
- 10–24: disadvantage ≈ `0.001398`.
- 25+: disadvantage shrinks to ≈ `0.000463`, but does not reverse.

Interpretation: **cold start is a major part of the ATP failure, but not the entire failure**. Pure isolated surface ratings throw away useful cross-surface information. ATP clay nevertheless contains evidence that surface specialization may contribute a conditional signal.

## WTA

Common known-surface population: **68,993 matches**.

| Metric | Overall Elo | Surface Elo | Surface change |
|---|---:|---:|---:|
| Accuracy | 65.9574% | 64.7254% | **-1.2320 pp** |
| Brier | 0.211973 | 0.217394 | **+0.005421 worse** |
| Log loss | 0.610757 | 0.623091 | **+0.012334 worse** |
| 10-bin ECE | 0.030170 | 0.023413 | lower ECE, but much worse proper scores |

Year stability:

- Surface Elo has worse Brier in **all 26 of 26 years**.
- Surface Elo has worse log loss in **all 26 years**.
- Accuracy is worse in 24 of 26 years.

By surface:

- Surface Elo is worse on Hard, Clay, Grass, and Carpet.

By weaker-player prior surface experience:

- the gap is largest at zero prior matches,
- it narrows with more history,
- but it remains worse even in the `25+` band (Brier disadvantage ≈ `0.003489`).

Interpretation: WTA results strongly reject pure independent Surface Elo as a replacement for overall Elo under this architecture.

---

# Decisions

## Promote

**Overall Elo** becomes the current core strength baseline for both ATP and WTA.

## Reject as general replacement

**Pure independent Surface Elo v1** is classified **D/Rejected as a general replacement for overall Elo**.

This rejection is architecture-specific. It does **not** mean surface is unimportant. It means `one completely separate rating universe per surface with no information sharing` is inferior.

## Register follow-ups

1. **Surface blend / shrinkage hypothesis** — test surface information as an adjustment to overall strength rather than a replacement. ATP clay is the clearest conditional candidate; WTA should require strong evidence before assigning meaningful surface-only weight.
2. **Chronological Elo calibration** — raw Elo carries stronger probability information but has worse fixed-bin ECE than rank-logit in EXP-001.
3. **EXP-003 opponent-adjusted serve/return** — proceed with the planned next core information family while retaining overall Elo as the benchmark.

No follow-up is permitted to rewrite EXP-001 or EXP-002 as if the new architecture had been the original hypothesis.

---

# What these findings do not establish

They do not show:

- sportsbook edge,
- profitability,
- fair-odds superiority to the betting market,
- optimal Elo parameters,
- optimal surface weighting,
- injury/context/news value,
- live-betting value,
- production readiness.

Those remain separate future hypotheses and validation stages.

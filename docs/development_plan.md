# Tennis Genome — Development Master Plan

## Purpose

Build a reproducible, leakage-resistant tennis probability engine that can later support market-aware betting decisions. The system must first prove that it can estimate calibrated pre-match probabilities and identify when it should abstain. Profitability is a downstream hypothesis, not an assumption.

The development order is intentionally conservative:

1. data correctness,
2. baseline prediction,
3. metric isolation,
4. player profiles,
5. historical alignment / Tennis Genome,
6. calibrated ensembles and abstention,
7. independent-model freeze,
8. market comparison,
9. forward paper betting,
10. only then broader context, automation, and production policies.

Complexity is promoted only when it produces reproducible out-of-sample information.

---

## Phase 0 — Research and experiment contracts

### Deliverables
- canonical feature registry,
- source registry and provenance rules,
- timestamp semantics,
- hypothesis registry,
- immutable model/prediction versions,
- untouched holdout policy,
- leakage tests in CI.

### Gate
No feature enters production research unless its availability time and missingness policy are defined.

---

## Phase 1 — Canonical historical dataset

### Objective
Transform source-specific winner/loser CSVs into a source-independent historical representation.

### Required tables
- `pre_match`: only information legal before the first point,
- `outcomes`: winner/score/retirement/walkover,
- later: `match_stats`, `player_snapshots`, `rankings`, `source_events`.

### Critical rules
- A/B orientation must be independent of outcome.
- Outcome columns never appear in a pre-match table.
- Raw source files are not silently edited.
- Every build records source hashes and schema version.
- Unknown/missing values remain explicit until fold-fitted preprocessing decides how to handle them.

### Gate
The same raw inputs must deterministically yield equivalent canonical tables and pass the quality gate.

---

## Phase 2 — Historical reconstruction and integrity

### Checks
- duplicate match IDs,
- player identity collisions,
- impossible/missing ranks,
- retirement/walkover semantics,
- surface inconsistencies,
- name-hash fallback identities,
- date coverage,
- duplicate source rows,
- source-specific ranking timestamp semantics,
- exact-time limitations.

### Conservative time rule
If only a date is known, the system must not invent same-day match order. Baseline ratings therefore freeze at the start of a date and apply all daily updates after predictions for that date.

### Gate
No experiment is publishable while critical integrity errors remain unresolved.

---

## Phase 3 — Prediction floor

Build the simplest models first:

- M0: 50/50,
- M1: rank-based probability,
- M2: ranking-points model,
- M3: overall Elo,
- M4: surface Elo,
- M5: Elo + surface Elo.

The first formal experiment is **EXP-001: Ranking vs Elo**.

### Evaluation
- Brier score,
- binary log loss,
- accuracy as a secondary metric,
- calibration by probability bucket,
- ATP/WTA separately,
- surface/tournament/ranking-band subgroups,
- retirement-inclusive and normal-completion views where appropriate.

### Gate
Every baseline is reproducible under chronological evaluation and is compared on the same match population.

---

## Phase 4 — Walk-forward evaluation engine

### Required behavior
- train only on the past,
- predict later periods,
- fit preprocessing/calibration only inside training history,
- preserve prediction artifacts,
- support yearly and finer chronological folds,
- output subgroup and calibration reports.

Random train/test splitting is not the primary evidence standard.

### Gate
An entire experiment can be rerun from a config plus canonical dataset without manual edits.

---

## Phase 5 — Metric Laboratory

Every candidate feature must pass the same protocol.

1. raw association,
2. data reliability and missingness,
3. correlation with existing features,
4. confounder map,
5. add-one test,
6. remove-one ablation,
7. residual/orthogonal signal where appropriate,
8. interaction tests,
9. chronological validation,
10. calibration impact,
11. stability by season/surface/tour/player group,
12. uncertainty and sample-size reporting,
13. promotion/rejection decision.

### Metric grades
- **A Core** — stable incremental signal,
- **B Conditional** — useful only in identifiable contexts,
- **C Experimental** — promising but unproven,
- **D Rejected** — no reliable incremental value.

Rejected hypotheses remain recorded so they are not endlessly rediscovered.

---

## Phase 6 — Core factor research order

Recommended priority:

1. ranking,
2. overall Elo,
3. surface Elo,
4. opponent-adjusted serve,
5. opponent-adjusted return,
6. recent underlying form,
7. workload,
8. rest,
9. age/career state,
10. age × workload/rest,
11. handedness,
12. H2H incremental value,
13. tournament/surface context,
14. style/matchup interactions.

Factors such as injury NLP, social/news context, weather detail, travel, equipment, and psychological narratives remain later-phase until the structured core is stable.

---

## Phase 7 — Serve/return engine

Build opponent-adjusted serve and return strength rather than relying only on raw percentages.

Target decomposition:

`server ability × returner ability × surface/context -> point-on-serve probability`

Then validate whether point-level probabilities improve hold, set, and match probabilities beyond Elo.

### Gate
Serve/return features must improve future probability quality, not merely explain historical winners.

---

## Phase 8 — Player Profile v1

Profiles are time-versioned snapshots, not permanent labels.

Candidate dimensions:
- overall strength,
- surface strength,
- serve/return strength,
- recent underlying form,
- age/career state,
- workload/rest,
- surface tendencies,
- style features when reliable.

### Profile Gap experiment

`ProfileGap = profile-derived strength - Elo strength`

Test whether the gap predicts future 1/5/10/20-match performance, especially for improving, declining, or recently inactive players.

---

## Phase 9 — Match Fingerprint / Tennis Genome v1

Represent each match with both absolute and comparative state:

- A values,
- B values,
- A-B differences,
- interaction features,
- module-level feature families.

Initial modules:
- strength,
- serve/return,
- surface/environment,
- current form,
- workload/rest,
- player profile,
- matchup/style,
- context/data quality.

The visual fingerprint is a rendering of the mathematics; visual similarity never defines model similarity.

---

## Phase 10 — Historical Alignment Engine

Start with transparent similarity methods:

1. standardized Euclidean distance,
2. validated feature weights,
3. Mahalanobis distance,
4. learned embeddings only after simple methods are benchmarked.

All neighbor searches are strictly historical relative to the target match.

### Key experiment
Use neighbors to predict **residual performance beyond the baseline**, not merely raw winner frequency.

If similar historical structures do not improve future baseline probabilities, the Genome similarity layer is not promoted.

---

## Phase 11 — Motifs and local/module matching

Search for recurring feature combinations only after the baseline and metric lab are trustworthy.

Every discovered motif becomes a registered hypothesis and must be tested on data not used to discover it. Multiple-hypothesis controls apply.

---

## Phase 12 — Out-of-distribution and uncertainty

Estimate whether a new match resembles the training distribution.

Inputs may include:
- historical-neighborhood density,
- feature missingness,
- ensemble disagreement,
- data-source reliability,
- player-history depth.

The system must be allowed to say **PASS / insufficient evidence**.

---

## Phase 13 — Ensemble and calibration

Potential probability generators:
- Elo,
- surface Elo,
- serve/return model,
- profile model,
- conventional ML model,
- historical-neighbor model,
- later simulation/context models.

A meta-model may combine them only under chronological validation.

Calibration candidates:
- logistic/Platt scaling,
- isotonic regression,
- beta calibration if justified.

Calibration is fitted only on prior data.

---

## Phase 14 — Selective prediction

Measure the predictability frontier rather than assuming a single tennis accuracy number.

Report probability quality and winner accuracy at multiple coverage levels:

- 100%,
- 75%,
- 50%,
- 25%,
- 10%,
- 5%.

The system succeeds only if higher confidence corresponds to measurably stronger future performance.

---

## Phase 15 — Freeze independent model v1

Create an immutable market-free benchmark, e.g. `TGE-Independent-v1`.

It must use no sportsbook odds. This allows later measurement of whether Tennis Genome independently understands tennis or simply copies market information.

---

## Phase 16 — Market-aware layer

Collect timestamped:
- opening/current/closing odds,
- bookmaker/exchange,
- market type,
- available price,
- major line movements,
- market margin.

Convert odds to implied probability and estimate no-vig market probabilities.

`edge = model_probability - no_vig_market_probability`

Win probability alone is not a bet signal.

---

## Phase 17 — Decision and policy laboratory

A candidate decision may depend on:
- estimated edge,
- uncertainty,
- calibration quality,
- historical density,
- ensemble disagreement,
- data quality.

Test multiple policies rather than selecting one after seeing profit.

No policy is promoted based on in-sample ROI.

---

## Phase 18 — Forward paper betting

Daily lifecycle:

`collect -> T0 snapshot -> fingerprint -> probability -> market snapshot -> decision -> immutable lock -> result -> evaluation`

Track:
- Brier/log loss,
- calibration,
- accuracy,
- CLV,
- EV,
- realized ROI,
- drawdown,
- edge/confidence buckets,
- sample size.

A short profitable run is not proof of durable edge.

---

## Phase 19 — Context and environment

Only after the structured engine is validated, add evidence-tagged event classes such as:
- injuries/illness,
- coaching changes,
- practice restrictions,
- travel disruption,
- environment/court speed/weather,
- equipment changes,
- public comments/current events.

An LLM may extract structured facts, but it must not invent probability adjustments. Historical validation determines whether an event class deserves weight.

---

## Phase 20 — Interface and automation

Later layers may include:
- Tennis Genome visualization,
- historical-neighborhood explorer,
- sportsbook screenshot parsing,
- multi-market routing,
- research-agent hypothesis generation,
- multi-sport parent architecture.

The researcher may propose changes; it may not approve its own production deployment.

---

# Promotion pipeline

Every idea follows:

`idea -> observed association -> controlled relationship -> incremental predictive value -> chronological validation -> multi-period stability -> ablation -> adversarial review -> calibration benefit -> forward paper test -> production`

Skipping a stage requires an explicit written exception and prevents the result from being called validated.

---

# Version milestones

| Version | Milestone |
|---|---|
| v0.1 | canonical historical dataset + integrity gates |
| v0.2 | ranking/Elo baselines + EXP-001 |
| v0.3 | surface Elo |
| v0.4 | opponent-adjusted serve/return |
| v0.5 | Metric Laboratory automation |
| v0.6 | Player Profile v1 |
| v0.7 | Tennis Genome historical alignment |
| v0.8 | ensemble + calibration + OOD |
| v0.9 | selective prediction frontier |
| v1.0 | frozen independent tennis probability engine |
| v1.1 | market collection and no-vig layer |
| v1.2 | policy/EV decision engine |
| v1.3 | forward paper betting |
| v1.4+ | context, environment, visualization, automation |

---

# Immediate critical path

The current development branch should complete these in order:

1. canonical source adapter,
2. outcome-independent A/B orientation,
3. raw -> Parquet builder with provenance hashes,
4. integrity audit,
5. date-batched Elo walk-forward evaluator,
6. prior-year ranking calibration,
7. EXP-001 runner,
8. synthetic leakage tests,
9. real-source provenance/license/timestamp audit,
10. first canonical ATP/WTA dataset build,
11. EXP-001 report,
12. only then surface-Elo implementation/tuning.

The project should resist the temptation to skip directly to sophisticated models before the first baseline report is trustworthy.

---

# Development definition of done

A development unit is not done merely because code runs. It is done when:

- behavior is documented,
- tests cover the main failure mode,
- leakage implications are understood,
- CI passes,
- outputs are reproducible,
- assumptions are labeled as assumptions,
- no unverified hypothesis is described as established fact.

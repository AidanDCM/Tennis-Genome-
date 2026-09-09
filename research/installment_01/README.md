# Deep Research Installment 01

## Foundations, Baselines, and the First Predictive Factors

### Mission

Build the first defensible statistical foundation for Tennis Genome.

Installment 01 must determine:
- how strong basic baselines are;
- which first feature families provide incremental predictive information;
- which ideas are redundant/noisy;
- how much uncertainty remains;
- whether selective prediction can identify easier vs harder matches;
- whether historical-neighborhood information adds value beyond conventional baselines.

The goal is not to prove profitability yet.

## Scope

Primary:
- professional singles tennis
- ATP and WTA main-tour matches
- Grand Slams
- completed matches

Secondary/later within installment if data quality allows:
- qualifying
- Challenger / WTA 125
- ITF

Retirements, walkovers, defaults, and incomplete matches require explicit outcome/status handling and should not silently join ordinary completed-match labels.

## Core research target

Let `p_baseline` be the probability from the accepted current model.

Research new metrics against the residual information not already explained by that baseline.

Simple outcome diagnostic:

`residual = y - p_baseline`

Where richer point/game performance data exist, use continuous residual targets as well.

## Model ladder

### M0 — Ranking
Basic ranking/ranking-point probability baseline.

### M1 — Overall Elo
Pre-match Elo with explicit update order and tunable K/initialization choices validated chronologically.

### M2 — Surface Elo
Overall Elo + surface-specific rating with shrinkage/decay choices.

### M3 — Serve / Return
Opponent-adjusted serve and return strength, preferably point-based where data support it.

### M4 — Recent Form
Recent opponent-adjusted underlying performance with tested windows/decay.

### M5 — Player Profile
Profile-derived current strength and profile-gap experiments.

### M6 — Workload / Rest
Recent workload/rest variables and pre-registered interactions such as age × fatigue.

### M7 — Tennis Genome Neighborhood
Historical similarity/residual-neighborhood features.

### M8 — Calibrated Ensemble
Combine complementary accepted models, then calibrate chronologically.

## Experiment execution order

### EXP-001 Ranking vs Elo
Question: Does Elo improve probability quality over ranking/ranking points?

### EXP-002 Surface Elo
Question: Does surface-specific strength add stable information beyond overall Elo?

### EXP-003 Opponent-adjusted serve/return
Question: Do serve/return ratings materially improve the Elo stack?

### EXP-004 Recent-form windows
Compare 7/14/30/60/90/180/365-day windows and exponential decay, using opponent-adjusted underlying performance.

### EXP-005 Previous-match workload
Test previous-match duration/sets/games/points after baseline strength controls.

### EXP-006 Rest duration
Test hours/days since previous match, including nonlinear thresholds.

### EXP-007 Age × fatigue
Test whether workload/rest effects differ by age/career stage.

### EXP-008 Head-to-head incremental value
Test whether H2H adds future predictive information after Elo, surface, serve/return, and recency controls. Shrink aggressively.

### EXP-009 Profile Gap
Create independent profile-strength estimate and test whether `profile_strength - elo_strength` predicts future residual performance.

### EXP-010 Model disagreement
Test whether disagreement among independently trained models predicts error/uncertainty.

### EXP-011 Historical-neighborhood similarity
Test kNN/weighted neighborhoods on pre-match fingerprints, strictly historical retrieval only.

### EXP-012 Residual-neighborhood model
Predict baseline residuals from historical neighborhood structure.

### EXP-013 Neighborhood density / OOD
Test whether sparse neighborhoods correspond to worse calibration and whether density improves abstention.

### EXP-014 Calibration methods
Compare uncalibrated, logistic/Platt, isotonic, and other justified calibrators chronologically.

### EXP-015 Selective prediction
Build performance-vs-coverage curves. Determine whether high-confidence subsets are genuinely more accurate/calibrated.

### EXP-016 Family ablation
Remove strength, serve, return, form, workload, and genome families one at a time from the best accepted model.

### EXP-017 Symmetry
Verify predictions are invariant to arbitrary Player A/B ordering.

### EXP-018 Future-append leakage test
Verify historical features are unchanged when future matches are appended.

## Core comparison table

Every model report should include at minimum:

| Model | Log loss | Brier | Calibration | Accuracy | Coverage | N |
|---|---:|---:|---:|---:|---:|---:|
| M0 | | | | | 100% | |
| M1 | | | | | 100% | |
| M2 | | | | | 100% | |
| ... | | | | | | |

For selective prediction add threshold/coverage curves rather than a single accuracy number.

## Chronological protocol

Suggested structure (exact years depend on dataset coverage):

```text
training history -> validation window -> test window
roll forward and repeat
```

A final untouched period should remain unavailable during feature/model discovery.

Do not tune model or feature choices on that final period.

## Metric promotion

A candidate feature/family is promoted only when:
- legal at T0;
- reproducibly generated;
- meaningful data coverage;
- improves primary metrics or a clearly specified conditional subgroup;
- survives add-one and ablation tests;
- survives chronological validation;
- has acceptable uncertainty;
- does not rely on one tiny subgroup;
- passes adversarial review.

## Deliverables

Installment 01 should produce:

1. reproducible canonical historical dataset pipeline;
2. source/provenance registry;
3. metric registry v1 with grades;
4. Player Profile v1;
5. Match Fingerprint/Tennis Genome v1;
6. verified Elo and surface-Elo implementations;
7. serve/return strength model;
8. recent-form model;
9. workload/rest experiment suite;
10. historical-neighborhood baseline;
11. calibration framework;
12. selective-prediction framework;
13. prediction ledger schema;
14. hypothesis/pattern ledger;
15. leakage and data-quality tests;
16. walk-forward evaluator;
17. baseline research report with accepted/rejected findings.

## Success criteria

Installment 01 succeeds if we can:

- reconstruct a historical match's complete legal pre-match state;
- generate probability predictions without future leakage;
- reproduce ratings/features deterministically;
- compare model levels chronologically;
- quantify calibration and uncertainty;
- identify accepted vs rejected metric families;
- determine whether confidence/abstention separates easier from harder matches;
- determine whether historical similarity adds incremental value;
- preserve every prediction and experiment version.

## Failure criteria

Installment 01 is not complete if:
- random train/test splits remain the primary evidence;
- historical features change when future data are appended;
- model gains cannot survive ablation/chronological testing;
- probability calibration is not measured;
- the system reports winner accuracy without uncertainty;
- sportsbook odds are mixed into the independent baseline unnoticed;
- hypotheses are repeatedly re-tested until something appears significant.

## Deferred to later installments

- deep injury/news NLP
- social media context
- relationship/personal events
- detailed weather feeds
- ball/equipment modeling
- live match prediction
- screenshot/OCR sportsbook ingestion
- automated bet execution
- stake optimization
- self-modifying production agents
- full multi-sport parent system

## Governing principle

The first engine is built to determine which ideas deserve to survive, not to prove them.

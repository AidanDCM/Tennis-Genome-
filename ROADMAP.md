# Tennis Genome Roadmap

## Phase 0 — Research contract and repo foundation

Status: in progress

Deliverables:
- mission/governing principles
- architecture
- metric registry
- Player Profile spec
- Tennis Genome spec
- leakage rules
- validation protocol
- profitability framework
- schemas
- experiment registry
- Python project skeleton

Exit criterion: project can begin implementation without relying on undocumented chat context.

## Phase 1 — Canonical historical data

Build:
- source registry
- player identity resolver
- event/match normalization
- ranking snapshots
- match outcomes/status policy
- match stats pipeline
- data manifests
- quality checks

Tests:
- duplicate matches
- impossible chronology
- unresolved player IDs
- inconsistent surfaces/events
- missingness summaries

Exit criterion: reproducible canonical professional singles dataset.

## Phase 2 — Baseline ratings

Implement:
- ranking baseline
- Elo
- surface Elo
- walk-forward evaluator
- calibration plots/metrics

Exit criterion: verified M0-M2 benchmark report.

## Phase 3 — Serve/return and recent form

Implement:
- point/match-stat feature builder
- opponent-adjusted serve/return model
- form windows and decay
- family ablations

Exit criterion: M3-M4 report with accepted/rejected features.

## Phase 4 — Player Profile v1

Implement:
- time-aware snapshots
- strength/profile fields
- profile quality
- Profile Gap challenger

Exit criterion: determine whether profile-derived strength predicts future residual performance beyond accepted baselines.

## Phase 5 — Workload/rest/fatigue

Implement:
- workload windows
- rest calculations
- scheduling features
- age × fatigue and registered interactions

Exit criterion: classify workload/rest metrics A/B/C/D.

## Phase 6 — Tennis Genome v1

Implement:
- Match Fingerprint builder
- standardized family vectors
- historical-only neighbor index
- kNN/weighted distance baselines
- neighborhood residuals
- density/OOD measures
- visual fingerprint prototype later

Exit criterion: determine whether historical similarity adds incremental chronological value.

## Phase 7 — Ensemble, calibration, abstention

Implement:
- model stacking/averaging
- calibrator comparison
- uncertainty features
- model disagreement
- selective prediction
- PASS reason codes

Exit criterion: calibrated probability engine with performance-vs-coverage curve.

## Phase 8 — Market-aware paper engine

Implement separately:
- odds ingestion
- no-vig calculations
- market snapshots
- model-market edge
- EV calculations
- decision-policy versions
- immutable paper bet ledger
- CLV tracking

Exit criterion: forward/paper process that evaluates decisions without altering the independent tennis model.

## Phase 9 — Profitability research

Test:
- edge thresholds
- uncertainty-adjusted edges
- disagreement/density filters
- confidence buckets
- market types
- stability across seasons/tours/surfaces

Exit criterion: determine whether any policy exhibits robust out-of-sample positive EV/CLV/ROI with acceptable uncertainty. No profitability claim before this.

## Phase 10 — Rich contextual research

Potential additions only if foundations justify effort:
- injuries/health feeds
- travel/circadian data
- weather/altitude/court pace
- coaching changes
- equipment/balls
- credible current-event NLP

Each enters through the Metric Laboratory.

## Phase 11 — User interface / sportsbook screenshot workflow

Potential pipeline:
- screenshot/vision extraction
- match/market normalization
- match-ID resolution
- engine query
- probability/edge/confidence display
- visual Tennis Genome

Manual bet placement remains default until policy robustness and operational safety are proven.

## Phase 12 — Multi-sport parent system

After tennis methodology is validated, replicate the research architecture for baseball/basketball/etc. rather than sharing sport-specific formulas blindly.

Parent system can compare:
- calibration
- CLV
- ROI
- sample size
- uncertainty

across sport/market engines and allocate research attention based on evidence.

# Metric Registry v1

Status: design registry, not proof of usefulness.

Every metric starts as a candidate. Grade changes only after standardized testing.

Required metadata per metric:
- `metric_id`
- human definition
- formula
- unit / scale
- direction semantics
- source(s)
- `observed_at`
- `available_at`
- `collected_at`
- missingness behavior
- reliability grade
- candidate confounders
- candidate interactions
- current evidence grade (A/B/C/D)

## 1. Fundamental player strength

Candidates:
- ATP/WTA ranking
- ranking points
- overall Elo
- surface Elo
- strength of schedule
- opponent-adjusted win rate
- opponent-adjusted point win rate
- game/set win rates
- ranking-band performance
- tour-level transition indicators

Primary questions:
- Elo vs ranking
- surface Elo incremental value over overall Elo
- point-based strength vs match-result-based strength

## 2. Serve quality

Candidates:
- first serve in %
- first serve points won %
- second serve points won %
- overall serve points won %
- hold %
- ace % / aces per service point
- double-fault %
- break points saved %
- unreturned serve % where available
- serve velocity / placement / spin where available
- pressure-split serve performance
- rolling and surface-specific variants

Research note:
Raw serve statistics must be opponent-adjusted where possible. A strong server facing weak returners can otherwise appear stronger than a comparable player facing elite returners.

## 3. Return quality

Candidates:
- return points won %
- first-serve return points won %
- second-serve return points won %
- break %
- break-point generation rate
- break-point conversion %
- return depth / return position where available
- rolling/surface/opponent-adjusted variants

## 4. Rally and style

Experimental until data quality supports them:
- rally-length distributions
- forehand/backhand winner/error profiles
- forced/unforced error rates
- shot speed/spin/depth
- aggression index
- defensive tolerance
- net-point frequency/win rate
- approach frequency
- serve-and-volley frequency
- drop-shot/slice frequency
- average court position
- archetype/embedding labels

## 5. Direct matchup geometry

Candidates:
- Player A serve strength vs Player B return strength
- Player B serve strength vs Player A return strength
- handedness pairing
- forehand/backhand interaction
- rally-length preference mismatch
- net attacker vs passer
- topspin/contact-height compatibility
- movement / court-coverage interaction
- height/reach interaction

Most belong in interaction models rather than as isolated main effects.

## 6. Surface and court behavior

Candidates:
- nominal surface (hard/clay/grass/etc.)
- indoor/outdoor
- tournament-specific pace proxy
- historical hold/ace/break rates at event
- court identity if meaningful
- roof status
- bounce/friction proxies where reliable
- manufacturer/resurfacing information where reliable

## 7. Environment

Later/conditional candidates:
- altitude
- temperature
- heat index / WBGT
- humidity
- wind speed / gusts
- precipitation
- sunlight/shadow conditions
- barometric pressure
- roof open/closed
- local match time

All require timestamp alignment with match start and source-quality tracking.

## 8. Equipment / balls

Experimental:
- tournament ball manufacturer/model
- ball changes
- racquet/string changes
- footwear changes

Do not promote anecdotal equipment information without reliable timestamps and replication.

## 9. Recent underlying form

Candidates:
- opponent-adjusted point performance
- opponent-adjusted serve/return performance
- Elo change
- performance residual trend
- serve-speed trend where available
- error-rate trend where available

Candidate windows:
- 7d
- 14d
- 30d
- 60d
- 90d
- 180d
- 365d

Also test continuous exponential decay rather than arbitrary windows.

## 10. Workload, rest, fatigue

Candidates:
- hours since previous match
- previous-match minutes
- previous-match sets/games/points
- workload in prior 24h/48h/72h/7d/14d/30d
- consecutive playing days
- number of matches in recent periods
- long-match count
- tiebreak/five-set load
- singles+doubles workload where available
- late finish / next-start turnaround

Expected to require interactions with age, surface, temperature, physical profile, injury state, and career stage.

## 11. Health / injury

Potentially high-value but data-quality-sensitive:
- body part
- side
- injury type
- severity
- first report date
- most recent report date
- days since injury
- withdrawal/retirement history
- medical timeouts
- tape/brace observation if credibly timestamped
- surgery/recovery
- practice restriction
- serve/movement deterioration
- recurrence history

Every record must include source reliability and uncertainty. Post-match explanations cannot leak into pre-match state.

## 12. Travel / sleep / circadian

Experimental:
- previous location
- travel distance
- time-zone difference
- travel direction
- arrival date
- acclimation time
- match local time
- estimated body-clock time
- reported sleep disruption where credible

These must be tested rather than assumed to matter.

## 13. Career / physical profile

Candidates:
- age at T0
- height
- weight where reliable
- reach where reliable
- handedness
- backhand type
- years professional
- tour experience
- injury history
- comeback status
- career-stage features

## 14. Tournament / scheduling context

Candidates:
- tour
- event
- level
- round
- draw size
- qualifying/main draw
- seed
- wildcard / lucky loser
- best-of-3 / best-of-5
- deciding-set rules
- Grand Slam indicator
- home-country indicator
- court assignment
- scheduled/local start time
- rain/delay effects
- double-day scheduling

Incentive narratives (defending points, milestones, etc.) remain experimental unless translated into robust pre-match data and validated.

## 15. Pressure / psychological performance

Use shrinkage aggressively.

Candidates:
- tiebreak residual performance
- deciding-set residual performance
- serving-for-set/match residuals
- break-point performance beyond baseline
- comeback/lead-protection residuals
- favorite/underdog residual behavior

Raw clutch percentages are highly vulnerable to small-sample noise and selection effects.

## 16. Human / current-event context

Deferred from Installment 01 except for schema design.

Candidates:
- coaching change
- trainer/physio change
- illness
- bereavement
- family event
- legal/suspension/visa issue
- public controversy
- retirement announcement
- burnout statement
- injury statement
- preparation statement
- credible practice-status report

Every event requires:
- event type
- source
- source reliability
- certainty
- severity
- mechanism hypothesis
- first-known timestamp
- recency
- affected player
- expiry/decay assumption

The system must never convert gossip into a deterministic probability adjustment.

## Separate market registry

Market variables must never enter independent-model experiments unless explicitly testing a market-aware model.

Candidates:
- bookmaker
- market type
- opening odds
- current odds
- closing odds
- timestamped line movements
- consensus odds
- exchange/sharp proxy if available
- liquidity where available
- implied probability
- no-vig probability
- bookmaker margin

## Data-quality fields

Every derived feature should inherit or compute:
- source count
- source reliability
- completeness
- effective sample size
- recency
- missingness indicator
- uncertainty estimate

Missingness itself may be informative but must be handled explicitly and tested for stability.

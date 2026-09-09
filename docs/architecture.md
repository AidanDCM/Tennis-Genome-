# System Architecture

## Objective

Tennis Genome separates three problems that must not be conflated:

1. **Prediction** — estimate calibrated pre-match outcome probabilities.
2. **Decision** — decide whether a market price differs enough from fair value to justify action.
3. **Risk/profitability** — determine whether a betting policy survives uncertainty, variance, vig, and out-of-sample validation.

A prediction can be correct but unprofitable. A prediction can also lose while having been a good positive-EV decision. Evaluation must respect this distinction.

## Data flow

```text
sources
  -> canonical IDs
  -> raw immutable ingestion records
  -> cleaned event/match tables
  -> time-aware player snapshots
  -> pre-match state builder
  -> feature families
  -> model-specific matrices
  -> independent probability models
  -> calibration layer
  -> uncertainty + disagreement
  -> selective prediction / PASS
  -> optional market-aware layer
  -> immutable prediction ledger
  -> post-match evaluation
  -> research ledger / model promotion gate
```

## Layer 1: Canonical data

Core entities:
- player
- tournament/event
- match
- match outcome
- point/game/set aggregates where available
- player snapshot
- pre-match state
- source/provenance record

Every time-dependent record must carry at minimum:
- `observed_at`
- `available_at`
- `collected_at`
- `source_id`
- `reliability_grade`
- `known_before_t0`

`available_at` is the critical leakage field: it answers when the information could actually have been used by a historical pre-match prediction.

## Layer 2: Player Profile

A Player Profile is not one timeless row. It is a versioned snapshot.

Slow-changing traits:
- date of birth / age at snapshot
- handedness
- height / reach where reliable
- backhand type where reliable
- career stage

Dynamic strength/state:
- overall Elo
- surface Elo
- opponent-adjusted serve strength
- opponent-adjusted return strength
- recent underlying performance
- workload/rest state
- injury/availability state if reliable
- style/archetype features where supported

Every historical match must use the latest valid snapshot available strictly before T0.

## Layer 3: Match Fingerprint / Tennis Genome

A Match Fingerprint is a deterministic pre-match representation of the matchup, initially built from validated feature families.

Example blocks:
- baseline strength differences
- surface-specific strength differences
- serve-v-return matchup
- recent-form differences
- workload/rest differences
- age/career interactions
- matchup/style interactions
- environment/context blocks when reliable
- data-quality and missingness indicators

The fingerprint is used by conventional models and by the historical-similarity engine. Visual rendering is secondary; mathematical similarity is primary.

## Layer 4: Independent models

Initial model ladder:

- M0 ranking baseline
- M1 overall Elo
- M2 overall + surface Elo
- M3 opponent-adjusted serve/return model
- M4 recent-form augmentation
- M5 Player Profile model
- M6 workload/rest/interactions
- M7 historical-neighborhood model
- M8 calibrated ensemble

Market odds are deliberately excluded from these models.

## Layer 5: Calibration

Raw model scores are not accepted as probabilities until tested/calibrated.

Candidate methods:
- logistic/Platt calibration
- isotonic calibration when sample size supports it
- beta calibration if justified

Calibration must be fit chronologically without peeking at evaluation periods.

Outputs:
- probability
- calibration bucket/history
- uncertainty interval or empirical uncertainty estimate
- model disagreement score
- historical-neighborhood density

## Layer 6: Selective prediction

The system must support `PASS`.

Abstention features may include:
- high model disagreement
- sparse historical neighborhood
- unreliable/missing critical data
- extreme out-of-distribution fingerprint
- wide uncertainty
- unstable calibration bucket

Research question: does error decrease materially as coverage decreases and only higher-confidence predictions are retained?

## Layer 7: Market-aware decision engine

Kept separate from the tennis model.

Inputs:
- independent model probability
- bookmaker prices / timestamps
- consensus or selected book
- market margin / vig
- no-vig implied probability
- model uncertainty
- decision-policy version

Derived quantities:

`edge_pp = p_model - p_market_novig`

For decimal odds `d`:

`EV_per_unit = p_model * (d - 1) - (1 - p_model)`

A bet is never generated merely because `p_model > 0.5`.

Decision gates can later test:
- minimum edge
- minimum lower-bound edge after uncertainty
- minimum data quality
- maximum model disagreement
- minimum neighborhood density
- minimum calibration reliability

## Layer 8: Immutable prediction ledger

Every historical paper/live prediction stores:
- prediction ID
- match ID
- model/version IDs
- data cutoff timestamp
- input fingerprint hash
- predicted probability
- uncertainty
- calibration version
- decision-policy version
- market snapshot if used
- action (`BET`/`PASS`)
- stake if applicable

Results are appended later; predictions are never rewritten after outcome is known.

## Layer 9: Researcher / Adversary / Evaluator

Researcher:
- proposes features, interactions, model changes, thresholds.

Adversary:
- searches for confounding, leakage, multiple-testing artifacts, temporal instability, subgroup collapse, and implausible effect sizes.

Frozen evaluator:
- tests on untouched chronological data unavailable to the researcher during discovery.

Promotion gate:
- promotes only changes that improve defined metrics with acceptable uncertainty and stability.

## Storage strategy

Preferred early stack:
- Parquet for immutable/processed analytical tables
- DuckDB for local analytical queries
- Python for pipelines/models/tests
- compact YAML/JSON only for configs and registries

Do not commit bulky raw datasets, model binaries, databases, or sportsbook screenshots to Git.

## Deferred architecture

Not required for Installment 01:
- sportsbook screenshot vision
- automated wager placement
- live in-match prediction
- deep news/social NLP
- autonomous self-modification
- detailed equipment/ball tracking
- full weather feeds
- relationship/personal-life inference

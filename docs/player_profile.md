# Player Profile v1

## Purpose

A Player Profile represents the player's state **as known at a particular time**. It is not a timeless biography and must never incorporate future information into historical matches.

## Snapshot semantics

Each profile snapshot has:
- `player_id`
- `valid_from`
- `valid_until`
- `computed_at`
- `data_cutoff`
- `profile_version`
- `source_coverage`

Historical prediction at T0 uses the newest snapshot whose data cutoff is strictly before or equal to the prediction cutoff.

## Slow-changing traits

Candidate fields:
- date of birth
- age at snapshot
- handedness
- backhand type
- height
- reach
- years professional
- career stage

Physical fields require source confidence and should not silently forward-fill through contradictory records.

## Dynamic strength

Core candidates:
- overall Elo
- hard/clay/grass Elo
- opponent-adjusted serve rating
- opponent-adjusted return rating
- recent point-performance rating
- recent Elo trend
- strength-of-schedule estimate

## Surface compatibility

Store both absolute and relative values:
- surface Elo
- surface performance residual vs overall expectation
- serve/return surface splits
- event/court-type history when samples permit

Avoid claiming a stable 'surface personality' from small samples.

## Style layer

Later/experimental candidates:
- serve dependence
- return dependence
- aggression
- rally tolerance
- net frequency/effectiveness
- movement/defensive profile
- rally-length distribution
- shot-pattern embeddings

Style values should carry effective sample size and uncertainty.

## Physical / durability state

Candidates:
- recent match minutes
- 24h/48h/72h/7d/14d workload
- rest hours
- consecutive playing days
- recent long-match count
- injury-state indicator
- injury recurrence indicator
- comeback/layoff duration

These describe current state, not an immutable player trait.

## Matchup sensitivity layer

Only after sufficient evidence:
- vs left-handed / right-handed opponents
- vs elite servers
- vs elite returners
- vs aggressive baseliners
- vs defensive profiles
- vs high/low rally-length profiles
- surface-specific matchup residuals

All sensitivity estimates require shrinkage toward population means.

## Profile Strength concept

The project will test a learned `profile_strength` distinct from Elo.

Elo answers roughly:
> How strong has this player been at winning matches against rated opponents?

Profile strength asks:
> Given the underlying serve, return, point, form, surface, workload, and validated profile features available now, how strong does the player appear independently of match-result Elo?

Define experimental:

`profile_gap = profile_strength - elo_implied_strength`

Hypothesis to test:
- positive profile gap may identify improving/underrated players;
- negative profile gap may identify declining/overrated players.

This is not assumed true until it predicts future residual performance.

## Profile quality

Every profile should carry:
- coverage score
- recency score
- effective sample size
- missing critical fields
- source reliability summary
- uncertainty estimate

Profiles with poor coverage should not be treated as equivalent to dense, recent profiles.

## Player symmetry

A match model should use comparable A/B fields and derive differences/interactions without encoding arbitrary player-order advantage.

Required property test:
Swapping A and B should produce the corresponding inverted probability within numerical tolerance for symmetric binary models.

## v1 acceptance threshold

Player Profile v1 is useful if profile-derived features improve chronological probability quality beyond Elo/surface Elo/serve-return baselines, or if Profile Gap predicts future residual performance in stable subsets.

# Historical Availability Audit 001 — Sackmann-style Research Source

Status: **machine-readable audit active; target-row availability unresolved; coverage report execution pending**

Audit date: 2026-09-14

## Purpose

This audit converts an important limitation from prose into executable research controls.

The current Sackmann-style adapter correctly separates target-row fields from post-match
outcomes/statistics, but physical separation is not the same as proof that a target-row
field was historically available before a specific match.

For v2 research, a field is canonical only when its point-in-time legality is established
by a `FeatureAvailabilityContract`.

## Source facts established strongly enough for this audit

The upstream ATP/WTA documentation describes ranking data and age in match-result rows as
being **as of `tourney_date`**. It also describes `tourney_date` as almost always the
Monday at or near the beginning of the event.

That does not establish the exact publication timestamp or exact availability before each
target match.

Primary upstream references:

- https://github.com/JeffSackmann/tennis_atp
- https://github.com/JeffSackmann/tennis_wta

The current project source audit also already records that exact same-day timing is not
verified and therefore freezes state for a full calendar date.

## Audit decisions

### Allowed for canonical v2 only under conservative prior-date chronology

- outcome-derived Elo state;
- opponent-adjusted serve/return state built from prior match statistics;
- result-form state;
- point-form state;
- workload state built from prior duration.

These inputs are legal only when every contributing source match occurred on a UTC date
strictly earlier than the target date.

They do **not** gain same-day legality from CSV row order or `match_num`.

### Explicitly unresolved for target-match canonical v2 use

- target ranking;
- target ranking points;
- target age;
- target event context such as surface, round, seed, entry and best-of;
- target player reference fields such as hand, height and IOC.

These fields may be perfectly reasonable research inputs, and some are almost certainly
known before a real match. The issue is narrower: the current historical source contract
does not yet prove their exact point-in-time availability and revision history strongly
enough for them to serve as canonical protected-v2 evidence.

They therefore receive `RESEARCH_ONLY_UNVERIFIED`, not an invented pre-match timestamp.

## Post-match observations

Match outcome, match statistics and duration are post-match observations.

They may update a player's later state but must not influence another target on the same
source calendar date while exact intraday ordering remains untrusted.

This is stricter than real tennis chronology but avoids manufacturing chronology from
source row order.

## Historical coverage audit status

The coverage metric is now frozen in
`tennis_genome.research_workbench.historical_coverage_audit` before the real year-by-year
report is opened.

For each tour/year it records, on an explicit non-walkover/non-retirement denominator:

- presence of any retained match-stat object;
- valid serve observations for each side and both sides using the fields actually consumed
  by the serve/return estimator;
- retained match duration used by workload state.

The coverage audit is `DESCRIPTIVE_ONLY`. It defines no bad-year threshold, removes no
year, changes no coefficient, and cannot itself upgrade a feature's T0 policy.

`scripts/run_historical_coverage_audit_real.sh` is the isolated real-data execution path.
It rebuilds only the exact pinned 2000–2025 ATP/WTA canonical snapshot, fails closed on the
archived row/hash identities, and runs only the coverage audit. It does **not** invoke the
sealed dynamic-state candidate search.

The real ATP/WTA coverage artifacts have not yet been opened from this execution path.
Any interpretation must occur only after the pinned launcher reproduces its source gates.

## Remaining work

1. Verify historical publication semantics for rankings/ranking points.
2. Verify whether target event context can be reconstructed from independently timestamped
   draws/schedules rather than retrospectively compiled match rows.
3. Audit player reference fields for historical revision behavior.
4. Execute the frozen historical coverage audit on the pinned source and archive the
   tour/year stats + duration coverage artifacts; do not derive exclusion/tuning rules
   from the observed coverage pattern.
5. Identify a source with trustworthy match-start timestamps for dynamic-state research.
6. Bind every canonical v2 dataset fingerprint to the exact availability-registry hash.

## Scientific consequence

The new v2 research program should not interpret the existence of a historical column as
proof of T0 legality.

Until stronger source evidence is added, the current source safely supports conservative
prior-date dynamic state more strongly than it supports exact target-match contextual
features.

This audit does not alter TGE-Independent-v1 or either frozen prospective protocol.

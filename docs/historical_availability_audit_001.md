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

### Ranking/ranking-points evidence review

`docs/historical_ranking_availability_evidence_001.md` records the dedicated review of the
ranking fields.

That review establishes the weekly Monday/event-date convention strongly enough for
provenance, including ATP evidence that official rankings are published on Monday. It does
not establish a trustworthy historical publication timestamp and revision ledger for each
snapshot represented in the pinned research source.

Accordingly, target ranking and target ranking points remain
`RESEARCH_ONLY_UNVERIFIED`. This is an audited negative conclusion, not pending permission
to assume a pre-match timestamp.

### Event-context evidence review

`docs/historical_event_context_availability_evidence_001.md` records the dedicated review of
surface, round, seed, entry and best-of.

Modern official ATP/WTA material shows that these kinds of values can exist before play:
official draw pages publish rounds, seeds and entry markers, and WTA's current tournament
interface states that final draws are confirmed three days before play starts. That supports
real-world pre-match plausibility.

It does not establish that the values in each pinned retrospective match row came from an
independently timestamped historical draw/schedule before that target match, nor does it
supply a version/revision ledger for those row values.

Accordingly, target surface, round, seed, entry and best-of remain
`RESEARCH_ONLY_UNVERIFIED` when sourced only from the pinned completed-match rows. This is
also an audited negative conclusion, not permission to infer a synthetic publication time.

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

## Availability-registry binding status

Canonical v2 `DatasetFingerprint` identity is structurally bound to
`availability_contract_sha256`.

The fingerprint constructor requires a valid lowercase SHA-256 availability identity and
includes it in the dataset digest. Changing only the availability-registry identity while
holding the ordered match population fixed therefore changes the dataset fingerprint.
Malformed or absent availability identities fail closed.

The current real dynamic-state runner passes the semantic hash of the audited Sackmann
availability registry into this required field. This means availability identity is part
of dataset identity rather than optional report metadata.

## Remaining work

1. Audit player reference fields for historical revision behavior.
2. Execute the frozen historical coverage audit on the pinned source and archive the
   tour/year stats + duration coverage artifacts; do not derive exclusion/tuning rules
   from the observed coverage pattern.
3. Identify a source with trustworthy match-start timestamps for dynamic-state research.
4. Revisit ranking/ranking-points canonical eligibility only if stronger historical
   publication/version evidence is obtained; the current evidence review does not justify
   promotion.
5. Revisit target event-context eligibility only if independently timestamped/versioned
   historical draw, schedule, order-of-play or provider snapshots are added and bound to T0.

## Scientific consequence

The new v2 research program should not interpret the existence of a historical column as
proof of T0 legality.

Until stronger source evidence is added, the current source safely supports conservative
prior-date dynamic state more strongly than it supports exact target-match contextual
features.

This audit does not alter TGE-Independent-v1 or either frozen prospective protocol.

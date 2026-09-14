# Historical Availability Audit 001 — Sackmann-style Research Source

Status: **initial machine-readable audit; canonical v2 target-row availability remains unresolved**

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

## Remaining work

1. Verify historical publication semantics for rankings/ranking points.
2. Verify whether target event context can be reconstructed from independently timestamped
   draws/schedules rather than retrospectively compiled match rows.
3. Audit player reference fields for historical revision behavior.
4. Quantify missingness/schema changes for match statistics and duration by tour/year.
5. Identify a source with trustworthy match-start timestamps for dynamic-state research.
6. Bind every canonical v2 dataset fingerprint to the exact availability-registry hash.

## Scientific consequence

The new v2 research program should not interpret the existence of a historical column as
proof of T0 legality.

Until stronger source evidence is added, the current source safely supports conservative
prior-date dynamic state more strongly than it supports exact target-match contextual
features.

This audit does not alter TGE-Independent-v1 or either frozen prospective protocol.

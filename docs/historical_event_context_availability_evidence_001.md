# Historical Event-Context Availability Evidence 001

Status: **EVIDENCE REVIEWED — MODERN PRE-MATCH EXISTENCE SHOWN; PINNED HISTORICAL T0 NOT ESTABLISHED**

Audit date: 2026-09-14

## Question

Can target-match event-context fields from the pinned Sackmann-style source—especially
surface, round, seed, entry and best-of—be promoted from `RESEARCH_ONLY_UNVERIFIED` to
canonical v2 pre-match inputs?

## What the historical research rows contain

The pinned match-result format contains tournament/event fields such as surface, draw size,
tournament level and date, plus per-match fields including seed, entry, best-of and round.
Their existence in a completed-match row establishes retrospective content, not the time at
which that content became known.

Upstream reference:

- https://github.com/JeffSackmann/tennis_atp

## Modern official evidence

Official ATP tournament pages expose draws, seeds, rounds, entry markers and tournament
surface/schedule context around live/current events. Official WTA tournament pages likewise
publish draws, and WTA's current tournament interface states that final tournament draws
are confirmed three days before play starts.

Representative official references reviewed:

- https://www.atptour.com/en/scores/current/roland-garros/520/draws
- https://www.wtatennis.com/tournaments/1077/jiujiang/2026/draws

This is useful evidence for the semantic proposition that these kinds of fields can be
pre-match information in real tennis operations.

It does **not** prove that the values contained in each pinned historical match row were
captured from a contemporaneous draw/schedule before that target match, nor does it supply a
versioned historical publication timestamp for those values.

## Field-level decision

### Surface

Tournament surface is normally fixed and publicly known before play. However the pinned
historical row does not preserve an independently timestamped source artifact proving the
historical value's publication/revision state.

Decision: `RESEARCH_ONLY_UNVERIFIED` for canonical target-row v2 use from this source.

### Round

Round is structurally part of a tournament draw and is visible on official draw material,
but retrospective match rows do not prove when the stored round assignment became available
or whether draw changes were later reconciled.

Decision: `RESEARCH_ONLY_UNVERIFIED`.

### Seed

Seed assignments are a draw input and normally known before main-draw play. The pinned row
does not preserve the contemporaneous draw version or publication timestamp from which its
seed value came.

Decision: `RESEARCH_ONLY_UNVERIFIED`.

### Entry

Entry markers such as qualifier, wild card and lucky loser can change close to play because
qualifying, withdrawals and lucky-loser insertion are operational processes. Retrospective
rows are especially weak evidence of exact T0 availability for this field.

Decision: `RESEARCH_ONLY_UNVERIFIED`.

### Best-of

Match format is generally governed by tournament/competition rules and is often knowable
before the match. But the pinned match-result row is still a retrospective source without an
independently retained rule/draw artifact bound to that target's T0.

Decision: `RESEARCH_ONLY_UNVERIFIED` from the pinned row alone.

## What would justify promotion

A future canonical historical pipeline may promote some of these fields if it reconstructs
them from independently timestamped evidence, for example:

1. archived official draw snapshots with capture/publication timestamps;
2. versioned tournament schedules/order-of-play files retained before the target match;
3. a licensed historical provider feed whose snapshot timestamps and revision semantics are
   documented and retained; or
4. immutable historical tournament metadata whose effective period is explicitly documented
   and can be bound to the target's prediction cutoff.

The availability contract should bind the identity of that source artifact, not simply copy
the value from the completed-match row.

## Scientific consequence

This review distinguishes two claims that must not be conflated:

- **real-world semantic plausibility:** these fields are commonly pre-match information;
- **historical evidentiary legality:** the pinned retrospective row proves they were known at
  the target cutoff.

The first is supported. The second is not yet established.

No field is promoted, no model or coefficient changes, no protected/prospective population is
opened, and TGE-Independent-v1 plus the frozen prospective protocols remain unchanged.

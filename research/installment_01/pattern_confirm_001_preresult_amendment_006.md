# PATTERN-CONFIRM-001 Pre-result Amendment 006 — Complete Season-Based State Capture

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

Amendment 005 froze the post-2025 dynamic-state source as Sportradar Tennis v3 completed ATP singles Sport Event / Season Summaries records. The initial operational coordinator draft used Daily Summaries as a transport shortcut. No real provider run was performed and no prospective row was admitted. This amendment resolves the transport detail in favor of the already-frozen Season Summaries source and adds an explicit completeness/cutoff contract before implementation.

No hypothesis threshold, correction, family alpha, O'Brien-Fleming boundary, look N, or promotion rule changes.

## 1. Catalog discovery

The state capture uses the Tennis v3 `Competitions` and `Seasons` feeds as one catalog snapshot.

A competition is eligible only when all are true:

- category ID is exactly ATP: `sr:category:3`;
- competition `type` is exactly `singles`;
- competition `level` is one of the Amendment-005 supported levels: `grand_slam`, `atp_1000`, `atp_500`, `atp_250`, `atp_world_tour_finals`, `atp_next_generation`.

A season is selected only when all are true:

- its `competition_id` resolves to exactly one eligible competition;
- `disabled` is not true;
- `start_date >= 2026-01-01`;
- `start_date < target season start date`.

The target season itself is therefore never part of its own state history.

## 2. Season Summaries completeness

Every selected season is fetched from the Tennis v3 `Season Summaries` endpoint. Pagination is deterministic with `limit=200` and `start=0,200,400,...` until a page returns fewer than 200 summaries.

The capture fails closed on provider/request/schema failure. A selected season cannot be silently skipped because of a partial response or failed page.

The capture artifact binds:

- Competitions response SHA-256;
- Seasons response SHA-256;
- sorted selected season IDs and start dates;
- every Season Summaries page SHA-256 and its `start` offset;
- the number of selected seasons and fetched pages;
- the target season-start cutoff;
- a deterministic self-hash.

## 3. Outcome-time leakage cutoff

Season start is the frozen canonical `event_date`, but provider outcomes still may not travel backward in time.

For a completed state-source event to update the target state, its provider `sport_event.start_time` must be strictly earlier than `00:00:00 UTC` on the target season-start date. This check is applied in addition to the existing requirement that the source season's canonical start date be strictly earlier than the target season start date.

Thus an overlapping earlier season cannot contribute a match that actually began on or after the target's frozen state boundary, even if that match is already completed when the package is captured later.

No `resume_time`, settlement timestamp, score timestamp or current capture time may rescue a row that fails this cutoff.

## 4. 2025-starting seasons

A provider season with `start_date < 2026-01-01` is not part of the post-2025 extension, even if one of its matches physically occurs in calendar 2026. This conservative exclusion avoids assigning a newly observed 2026 outcome to a pre-2026 canonical event date that was outside the frozen 2000-2025 source snapshot.

A future experiment may redesign this edge case, but PATTERN-CONFIRM-001 will not silently do so.

## 5. Reuse and caching

The catalog/Season-Summaries capture is separable from per-target context capture. A sealed state-capture artifact may be reused for multiple targets only when its target season-start cutoff is exactly the same as the target's frozen season-start date.

A later target season requires a newly sealed capture through that later season-start boundary. Previously fetched immutable provider bodies may be cached by content hash, but the final capture artifact must still prove complete season selection and pagination for its own cutoff.

## 6. No readiness claim yet

Synthetic tests and CI cannot convert this contract into real evidence. `READY_FOR_ACCUMULATION` still requires:

1. a credentialed two-snapshot Pinnacle/Sportradar transport dry run passing Amendment 003; and
2. a real sealed season-based state capture and target source package passing Amendments 004-006.

Until those artifacts exist and are reviewed, both hypotheses remain `ACCUMULATING, N=0`.

# PATTERN-CONFIRM-001 Pre-result Amendment 002 — Live Identity and Actual-Start Authority

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

Amendment 001 froze Pinnacle via `THE_ODDS_API_V4_PINNACLE_V1` as the scientific market benchmark but intentionally left the approved stable-ID event provider to be connected later. This amendment closes that remaining contract before prospective accumulation begins.

No hypothesis threshold, correction, sequential boundary, look N, family alpha or confirmation rule changes.

## 1. Provider roles are deliberately separate

### Market probability authority

- transport/provider contract: `THE_ODDS_API_V4_PINNACLE_V1`
- bookmaker: Pinnacle
- market: two-sided ATP singles match winner / head-to-head
- purpose: raw decimal prices, quote-provider timestamp, scientific market probability after frozen two-way de-vigging

### Event identity and timing authority

- provider contract: `SPORTRADAR_TENNIS_V3`
- category: ATP
- singles events only
- purpose: stable sport-event ID, stable competitor IDs, event status, confirmed schedule metadata and post-event timeline used for the actual-start audit

The market feed is not allowed to self-certify the match's actual start time. The event/timing authority is independent of the market snapshot used by the hypothesis.

## 2. Frozen event identity

A prospectively logged market event must be mapped before prediction commitment to exactly one Sportradar `sport_event.id` and exactly two Sportradar competitor IDs.

The mapping artifact must bind:

- The Odds API event ID;
- Sportradar sport-event ID;
- Pinnacle outcome orientation A/B;
- Sportradar competitor IDs A/B;
- canonical player IDs A/B;
- provider names used only as descriptive QA;
- mapping creation timestamp;
- mapping method/version;
- deterministic mapping self-hash.

Preferred mapping is an existing explicit provider-ID crosswalk. If no provider-ID crosswalk exists, an automated bootstrap resolver may use only pre-match descriptive identity: exact normalized unordered competitor names, ATP/singles context, competition/tournament context and scheduled-time proximity. It may resolve only when exactly one candidate event and orientation remain. No fuzzy/edit-distance tie-breaking, ranking, odds, Profile Gap, Core probability, result or performance information may choose among multiple candidates. Zero or multiple candidates fail closed and require a prospectively documented manual identity mapping before prediction commitment.

A manual mapping is identity administration, not model tuning: it may inspect only the same pre-match identity/context fields and must be created before the prediction is committed.

## 3. Pre-match schedule gate

At logging time the Sportradar event must be ATP singles and not live/ended. `start_time_confirmed=true` is required for the event to enter the confirmatory intake queue.

The current Sportradar `start_time` is stored as `scheduled_start`. Reschedules/replacements are tracked by stable sport-event provenance rather than silently creating a new match identity.

The Pinnacle quote still must satisfy the Amendment-001 T-minus-five scheduled checkpoint when logged.

## 4. Frozen definition of actual start

The final confirmation-eligibility audit does not use the original schedule as actual start.

For a settled Sportradar event, `provider_verified_actual_start` is the timestamp of the earliest `match_started` event in the Sportradar sport-event timeline for that same sport-event ID.

If a covered timeline does not contain a `match_started` event, the row does **not** receive a substitute actual-start estimate and is excluded from confirmatory N with reason `ACTUAL_START_UNVERIFIED`.

This is intentionally conservative. Scheduled `start_time`, `start_time_confirmed`, first score observation, settlement time or bookmaker market closure may not substitute for the timeline start event.

## 5. Final temporal eligibility

A settled row counts toward a sequential look only if all are true:

- the identity mapping still resolves to the same Sportradar event and competitors;
- a timeline `match_started` event exists;
- the frozen Pinnacle provider snapshot timestamp is at least five minutes before that actual-start timestamp;
- `prediction_committed_at` is strictly before the actual-start timestamp;
- the provider event was represented as pre-match at ingestion;
- all existing model/source/hash gates pass.

Otherwise the row remains in the immutable ledger as an auditable exclusion and contributes zero to confirmatory N.

## 6. Future in-play research is separate

Sportradar's live summary/timeline capabilities may later support an in-play research program. Those events are not legal features for `PATTERN-CONFIRM-001`. This experiment remains strictly pre-match.

## 7. Current state

At this freeze, the selected hypotheses remain prospective `N=0`. This amendment therefore fixes live identity and timing semantics before any eligible future result is spent.

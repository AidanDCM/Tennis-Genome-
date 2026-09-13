# PATTERN-CONFIRM-001 Pre-result Amendment 004 — Prospective Event-Date and Season Identity Semantics

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

Amendment 003 requires internally generated Profile/Core values from a legal prospective state. During implementation, an important source-semantic fact was reverified in the existing canonical adapter and feature engines: historical `PreMatchState.event_date` is the Sackmann `tourney_date`, and dynamic states intentionally freeze across that source/event-start date. It is **not** the actual match timestamp or round date.

This amendment freezes the prospective equivalent before live v3 is implemented. It does not change either selected hypothesis, correction, family alpha, sequential boundary, look N, or promotion rule.

## 1. Prospective `event_date`

For a real Sportradar-backed target match, the canonical prospective `event_date` is:

`Sport Event Summary -> sport_event_context -> season -> start_date`

It is **not**:

- the sport event's `start_time` calendar date;
- the first point / `match_started` date;
- the main-draw stage start date;
- the prediction timestamp; or
- an operator-supplied arbitrary date.

The frozen interpretation is chosen because it preserves the historical event-start-date semantics used to fit both frozen production mappings.

## 2. Same-season freeze

The live state history used for a target season must contain only completed source events whose canonical event date is strictly earlier than the target `season.start_date`.

Therefore, results from earlier rounds or earlier match days inside the same Sportradar season may **not** update Profile/Core state for another match in that season. This deliberately preserves the historical source-date freeze even though a live provider knows exact match chronology.

No within-season chronology may be manufactured to improve prospective performance.

## 3. Identity contract v2

Before a live row can enter the ledger, the verified identity/event object must additionally bind:

- Sportradar `season.id`;
- Sportradar `season.start_date`;
- Sportradar `competition.id`; and
- the existing stable sport-event and competitor IDs.

The fresh pre-match summary observed at prediction time must reproduce the same season ID, season start date, competition ID, event ID, competitor orientation, and scheduled start as the sealed identity mapping.

Missing season ID/start date fails closed.

## 4. Prospective target context

The internally generated target `PreMatchState` must bind to the same canonical players and season-start date as the live identity mapping.

Where production features require target context, the approved provider fields are:

- surface: Sportradar season info;
- competition level: Sportradar competition/season context, mapped deterministically to the existing canonical tournament-level vocabulary;
- round: Sportradar sport-event context round;
- best-of: Sportradar sport-event context mode;
- seed: Sportradar competitor seed when present;
- entry path: deterministic mapping from Sportradar `qualification_path` when present;
- age, height and handedness: Sportradar competitor profile;
- country code: Sportradar competitor/profile country code.

No outcome, live score, market price, Profile/Core output, or future information may supply or repair these context fields.

Unknown context values may remain missing only where the existing frozen transform has an explicit missing-data path. A non-empty but unrecognized categorical value must fail closed rather than be silently recoded.

## 5. Post-2025 dynamic-state source

The 2000–2025 base remains the already frozen canonical archive. The post-2025 extension used only to update dynamic state is a separate prospective state feed and must be sealed before accumulation.

The preferred operational source is `SPORTRADAR_TENNIS_V3_STATE_V1`, because the same provider supplies stable season/event/competitor IDs and completed-match statistics. Its implementation must preserve the fields actually needed by the frozen state engines:

- completed match orientation/outcome;
- season start date, surface, level, round, best-of and entry/seed context where required;
- stable player identity crosswalk to canonical IDs;
- service points won/lost (or an exact derivation of total service points), first- and second-serve points won;
- match duration when verifiable; missing duration remains missing, never zero;
- retirement/walkover status when available.

Historical target-rank fields are not permitted to be backfilled from a later ranking snapshot. Fields that are not required to update dynamic state remain missing unless observed at the legal source time.

Every state-source snapshot must be content-hashed and retained in the run provenance. Any unresolved or ambiguous canonical-player identity fails closed for that match; the readiness audit must report the resulting coverage rather than silently relabeling a player.

## 6. Readiness implication

`TRANSPORT_COMPATIBLE` remains only a provider transport result.

`READY_FOR_ACCUMULATION` additionally requires all of the following:

1. identity contract v2 (season ID/start date) is enforced;
2. a target pre-match context adapter is deterministic and tested;
3. the post-2025 dynamic-state source is frozen and hashed;
4. Profile/Core values are internally reproduced from the sealed state artifact;
5. the live envelope rejects externally injected signal values; and
6. the final helper-free branch passes normal CI.

Until those conditions are met, both hypotheses remain `ACCUMULATING, N=0` and no confirmatory row may be appended.

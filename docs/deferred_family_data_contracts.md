# Deferred Metric Families — Data Acquisition and Validation Gates

The pinned 2000–2025 research snapshot can support several foundational families, but it cannot honestly reconstruct every Tennis Genome factor. This document defines what must exist before the remaining families may enter historical testing.

These families are **blocked by data**, not rejected by evidence.

## Global rule

No deferred family may enter a pre-match model unless every observation can answer:

1. What was observed or reported?
2. Which player/match/venue does it apply to?
3. When did the underlying event occur?
4. When was the information first published or otherwise available?
5. When did our system collect it?
6. Was it available before the target match started?
7. How reliable is the source?
8. How certain is the extraction/mapping?
9. What plausible performance pathway does it represent?
10. Can the historical reconstruction be reproduced from an auditable source snapshot?

If publication timing is unknown, the observation is not legal for historical pre-match evaluation.

---

## Environment / court conditions

Schema: `schemas/environment_snapshot.schema.json`

Target variables include:
- altitude;
- temperature;
- humidity;
- wind;
- indoor/outdoor state;
- roof state;
- court-speed estimate;
- ball manufacturer/model.

### Preferred sources

Use official tournament/venue documentation for stable venue facts and timestamped weather providers for historical forecasts/observations. Court speed and ball information require their own source audit; do not infer them from surface labels alone.

### Critical historical distinction

A weather observation recorded after a match is not automatically a legal pre-match weather feature. The strongest design should reconstruct the forecast or information actually available before T0. If only realized weather is available, test it separately as descriptive/causal research, not as a leakage-free historical forecasting feature.

### First experiments

1. altitude as a modifier of serve/return point expectations;
2. temperature/humidity interactions with fatigue and age;
3. wind interaction with serve dependence;
4. indoor/outdoor and roof-state interactions;
5. court-speed / serve-return matchup effects when trustworthy measurements exist.

---

## Injury / health / coaching / current events

Schema: `schemas/context_event.schema.json`

This family includes:
- injury and illness;
- surgery/recovery;
- withdrawal/retirement signals;
- practice restrictions;
- coaching/trainer changes;
- equipment changes;
- travel disruption;
- visa/disciplinary issues;
- credible major personal events;
- public fitness/burnout/schedule statements.

### Evidence policy

The system must preserve facts separately from interpretation.

A context event may influence a model only when there is:
- a credible source;
- a pre-match publication timestamp;
- sufficient event certainty;
- a plausible performance mechanism;
- a historically testable class of comparable events.

Social-media posts and news summaries are evidence sources, not direct probability adjustments. An LLM may extract structured events; it may not invent an adjustment magnitude.

### First experiments

1. return from medically documented layoff;
2. pre-match withdrawal/injury reporting severity;
3. recent retirement/MTO history where timestamps are reconstructable;
4. coaching-change event study;
5. verified practice restriction / fitness statement classes.

All event-study effects require confounder controls and untouched future validation.

---

## Travel / time zones / circadian state

Schema: `schemas/travel_state.schema.json`

Required ingredients:
- reliable event location and timezone;
- prior event location;
- target match local time;
- travel distance;
- time-zone displacement;
- direction of travel;
- arrival/acclimation timing when available.

### Do not overclaim

Tournament sequence can estimate travel distance and timezone change, but arrival time and sleep/circadian state are usually uncertain. The representation must distinguish observed travel from inferred acclimation.

### First experiments

1. time-zone displacement after controlling for opponent strength/rest;
2. eastward vs westward travel;
3. distance × short turnaround;
4. travel × age;
5. match local time × estimated body-clock mismatch.

---

## Detailed style / tracking geometry

Schema: `schemas/style_snapshot.schema.json`

The current public match table supports only coarse handedness/height and point aggregates. The full style family requires richer tracking or point-by-point sources for features such as:
- aggression;
- rally length distribution;
- net frequency/efficiency;
- serve direction;
- return position;
- court position;
- spin/slice patterns;
- movement;
- first-strike efficiency.

Every style profile must be time-versioned. A 2025 profile cannot be attached retroactively to a 2018 match.

### First experiments

1. test each style dimension as a main effect only where meaningful;
2. prioritize matchup interactions over standalone style labels;
3. test whether style features improve serve/return and Elo rather than merely re-describe them;
4. use family-level ablation because tracking variables will be highly collinear;
5. later test learned style embeddings only after transparent baselines exist.

---

## Exact scheduling / true fatigue

The current source's `tourney_date` is event-start-era timing and is insufficient for true rest-hours reconstruction.

A higher-resolution schedule source should provide:
- scheduled start timestamp;
- actual start timestamp when possible;
- completion timestamp or duration;
- local timezone;
- rain/delay/resumption information.

Only after that upgrade should Tennis Genome claim to have tested:
- previous-match-to-next-match rest hours;
- same-event cumulative minutes/sets/points;
- consecutive-day effects;
- rain-delay/split-match recovery;
- age × true fatigue;
- heat × true fatigue.

The current `workload_rest_proxy` family is intentionally labeled a proxy and must never be presented as a complete fatigue test.

---

## Acquisition priority

Recommended order after the current foundational laboratory:

1. exact match scheduling/timestamps — unlocks true fatigue and better chronology;
2. venue/location/altitude — structured, stable, relatively auditable;
3. historical weather forecasts/observations — environment interactions;
4. structured injury/withdrawal/MTO sources — health layer;
5. travel/location reconstruction — circadian layer;
6. point-by-point/tracking data — detailed style and matchup layer;
7. news/coaching/current-event archive — highest timestamp/provenance complexity.

Priority can change if a commercially usable provider supplies several of these together.

---

## Promotion gate

Acquiring a field does not promote it.

Each new family still follows:

`source audit → timestamp audit → missingness audit → raw association → confounder map → add-one → full-model ablation → interactions → chronological validation → calibration impact → adversarial review → promotion/rejection`

The component that discovers the effect does not get to declare it successful.

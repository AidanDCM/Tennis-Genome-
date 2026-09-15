# Sportradar historical exact-time chronology admission 001

Status: **pre-result gate frozen before real historical provider coverage is opened**

This gate answers one narrow question:

> Can one retained Sportradar competition season be trusted as an exact **match chronology** source for historical research?

It does **not** admit a model, a player crosswalk, a canonical v2 dataset, a market source, or a protected comparison.

## Why the gate is frozen now

The historical provider audit can reveal attractive-looking coverage rates. Choosing a threshold such as 95%, 99%, or “close enough” after seeing those rates would make source eligibility outcome-dependent.

The frozen rule therefore uses no percentage threshold.

A season either supplies exact chronology for every played terminal match in its retained denominator or it does not enter the exact-time chronology panel.

## Required source package

Admission consumes `SPORTRADAR-HISTORICAL-START-TIME-AUDIT-002`.

Audit 002 wraps the original descriptive start-time audit while adding exact season identity. Every retained Season Summaries row must agree on:

- category ID and name;
- competition ID, name and type;
- season ID;
- season start date;
- `season.competition_id == competition.id`.

Mixed-season or mixed-competition evidence fails closed. A retained timeline for an event absent from the Season Summaries denominator also fails closed.

## Frozen chronology rule

For one season to receive `ADMITTED_EXACT_START_CHRONOLOGY_ONLY`:

1. the season must be an ATP (`sr:category:3`) or WTA (`sr:category:6`) main-tour **singles** competition;
2. no raw Season Summaries row may disappear from the in-scope denominator;
3. the season must be completed: no in-scope row may remain nonterminal;
4. there must be at least one played terminal match;
5. every played terminal match must contain exactly one valid, timezone-aware typed `match_started.time` in retained Sport Event Timeline evidence;
6. missing timelines, missing `match_started`, conflicting starts and invalid/naive start timestamps are all disqualifying;
7. walkovers remain retained but are outside the played-match exact-start denominator because no match was played;
8. a provider-updated `match_started` event is admissible only when its `updated_time` is also retained and valid;
9. scheduled `sport_event.start_time`, `start_time_confirmed`, and `estimated` remain diagnostics only and may never rescue missing actual-start evidence.

The effective coverage requirement is therefore structural 100% coverage of played terminal matches, not a tunable numeric threshold.

## Deterministic receipt

The admission verifier independently recomputes aggregate disposition counts and exact-start coverage from the event rows rather than trusting summary fields.

A successful receipt binds:

- raw audit-file SHA-256;
- semantic audit SHA-256;
- base descriptive-audit semantic SHA-256;
- frozen policy semantic SHA-256;
- provider season and competition identity;
- retained Season Summaries identity;
- retained timeline-bundle identity;
- played, exact-start, walkover and updated-start counts;
- SHA-256 identities of the base audit, season-bound audit and admission-verifier source files used to admit the season.

## What this does not prove

A chronology-admitted season is **not yet a canonical modeling panel**.

Before any protected v2 comparison can use a recent exact-time panel, separate pre-result controls must still establish:

- the complete inventory of accessible provider seasons and the rule for constructing the multi-season panel;
- canonical event/player crosswalk quality and failure handling;
- feature availability at target T0 for every additional source field;
- provider access and licensing/retention constraints;
- final dataset and code fingerprints;
- a registered development/protected evaluation procedure.

Seasons that fail this chronology gate remain authoritative source-quality negative evidence. They must not be silently repaired with scheduled starts or omitted without appearing in the source inventory.

## Relationship to long-history data

The intended architecture remains separate:

- Sackmann 2000–2025: long-history panel with conservative prior-date chronology;
- chronology-admitted Sportradar seasons: possible recent exact-time chronology panel;
- no silent mixing of timestamp semantics;
- no claim that results from either panel automatically transfer to the other.

This gate changes no TGE-Independent-v1 coefficient, prospective cohort, prospective metric, betting rule, or prospective sample count.

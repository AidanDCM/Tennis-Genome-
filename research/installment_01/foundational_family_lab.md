# Foundational Family Laboratory — Pre-Registered Contract

Status: **pre-registered before accepted real-data results**

Experiment ID: `FOUNDATIONAL-FAMILY-LAB-001`

This laboratory extends Installment 01 from one-feature-family experiments into a common chronological framework that can distinguish raw usefulness from unique usefulness after correlated families are present.

It is not a profitability test.

---

## Core benchmark

Every remaining family is tested against the same validated research core:

- overall Elo log-odds;
- opponent-adjusted serve/return matchup edge from EXP-003.

The core is chronologically recalibrated inside each historical training fold.

No sportsbook odds are available to this experiment.

---

## Why two tests per family

For family `F`, report both:

### Add-one test

`Core` vs `Core + F`

This asks whether the family contains predictive information beyond the current validated core.

### Remove-one / ablation test

`Full` vs `Full - F`

The full model contains every currently-supported foundational family. This asks whether `F` still contributes when correlated families are already present.

A family that looks useful in the add-one test but contributes nothing in full-model ablation is likely redundant, confounded, or replaceable by another family.

---

## Serve / return decomposition

EXP-003 validated the combined opponent-adjusted serve/return family. This laboratory additionally separates the learned components:

1. Elo only;
2. Elo + serve-rating difference;
3. Elo + return-rating difference;
4. Elo + serve-rating difference + return-rating difference.

This decomposition is diagnostic. It does not retroactively rewrite EXP-003.

---

## Family 1 — Recent form

Features:
- 30-day half-life Elo outcome residual difference;
- 90-day half-life Elo outcome residual difference;
- 30-day half-life opponent-adjusted point residual difference;
- 90-day half-life opponent-adjusted point residual difference.

The residual construction deliberately asks whether a player has recently performed above or below what Elo / point-strength expectations already predicted.

Same-source-date results update form only after every prediction on that date is frozen.

---

## Family 2 — Workload / rest proxy

Features:
- difference in gap from each player's previous known event date;
- log recent minutes difference over 7, 14, and 28 days;
- recent match-count difference over 14 and 28 days;
- log previous-event total minutes difference.

### Major timing limitation

The pinned source uses `tourney_date`, generally an event-start-era date, not a trustworthy exact match-start timestamp. Multiple rounds of one tournament can therefore share a date.

Consequences:
- same-event prior rounds are deliberately invisible to one another;
- recent minutes collapse toward the event date;
- exact rest hours are unavailable;
- the experiment tests **event-gap/workload proxies**, not true recovery time.

A weak result cannot reject the richer fatigue hypothesis. A strong result can justify acquiring higher-resolution timestamps.

---

## Family 3 — Age / career / physical

Features:
- age difference;
- difference in squared distance from age 27 as a simple nonlinear career-curve basis;
- young-player indicator difference (`<=23`);
- veteran indicator difference (`>=32`);
- height difference.

These are predictive features, not causal claims.

---

## Family 4 — Age × fatigue interaction

Features:
- centered age × log 14-day minutes difference;
- centered age × short-event-gap indicator difference.

This is the explicit H-007 interaction test. It is separated from the age main-effect family so fatigue moderation can succeed even if age alone adds little.

The same event-date timing caveat applies.

---

## Family 5 — Head-to-head

Features:
- Laplace-smoothed prior H2H edge;
- H2H edge weighted by log prior meeting count.

Only meetings on earlier source dates are available. Target-match and same-date outcomes are excluded.

The prior hypothesis is that H2H adds little after strong controls; a null/rejected result is scientifically useful.

---

## Family 6 — Handedness / basic matchup

Features:
- left-handedness directional difference;
- opposite-handed matchup × serve/return edge.

Height is tested in the age/career/physical family rather than duplicated here.

The source does not contain detailed shot geometry, return position, rally patterns, or stroke-level style. This is therefore a basic matchup test, not the final style model.

---

## Family 7 — Surface / tournament context

Pure Surface Elo already failed as a general replacement in EXP-002. This family asks a different question: does context alter the weight of already-useful strength signals?

Features include interactions of Elo / serve-return edge with:
- Hard;
- Clay;
- Grass;
- Carpet;
- Grand Slam level;
- Masters-level coding where supplied;
- tour-finals coding;
- lower-tier coding;
- late rounds;
- round robin;
- best-of-five format.

Player-specific tournament context also includes directional differences in:
- qualifier entry;
- wildcard entry;
- lucky-loser entry;
- protected-ranking entry;
- seeded status;
- inverse seed strength.

This does not include true court speed, altitude, ball model, temperature, humidity, or wind.

---

## Canonical-v3 data boundary

The research snapshot is rebuilt from the same pinned research-only source archive.

New legal pre-match source fields:
- age;
- handedness;
- height;
- IOC country code;
- seed;
- entry status;
- draw size.

New post-match-only field:
- match duration minutes.

Duration remains physically separated in the stats table and may affect future workload state only after its source date.

---

## Chronology

For every evaluated year:

1. build all states using only prior source dates;
2. train models only on earlier years;
3. fit missing-value imputation on the training fold only;
4. fit scaling on the training fold only;
5. fit logistic coefficients on the training fold only;
6. predict the held-out future year;
7. append immutable probabilities to the report.

No random train/test split is a primary result.

---

## Common population

Core, add-one models, full model, ablations, and serve/return decomposition must all be scored on the same eligible future match population.

Missing optional fields are handled by training-fold median imputation plus training-derived missingness indicators rather than dropping different matches for different families.

---

## Primary metrics

1. Brier score;
2. binary log loss.

Secondary / diagnostic:
- accuracy;
- 10-bin ECE;
- number of future seasons in which add-one Brier improves;
- number of future seasons in which add-one log loss improves.

---

## Interpretation rules

Classification is tour-specific.

### A — Core candidate

Normally requires:
- aggregate add-one Brier improvement;
- aggregate add-one log-loss improvement;
- positive Brier and log-loss contribution in full-minus-family ablation;
- add-one Brier improvement in at least roughly 70% of evaluated seasons;
- no obvious collapse in the most recent multi-season block.

### B — Conditional / low-weight candidate

Evidence is directionally useful but weaker, conditional, redundant in some tests, or materially different across eras/tours.

### C — Experimental

Mixed signs, weak effect, insufficient stability, or value visible only in exploratory slices. Do not promote to the production research core.

### D — Rejected under current representation

The family worsens aggregate probability quality or fails both add-one and ablation tests with adequate sample size.

Rejection is always scoped to the representation and data quality tested. It does not prove the underlying real-world concept has no effect.

---

## Explicitly blocked families in this source

Do not synthesize or infer these from names/scores:

- weather / temperature / humidity / wind;
- altitude / true court speed / ball type;
- injury / health state;
- travel / time zones / circadian state;
- coaching changes / current events;
- detailed style / tracking geometry.

They require later, timestamp-audited data acquisition.

---

## No post-result tuning

The first accepted run uses the feature definitions and model family above. If results suggest alternate half-lives, nonlinearities, thresholds, surface interactions, or parameter changes, those become new registered experiments.

The original laboratory result remains unchanged.

# Source Audit 001 — Historical Match Data

Status: **research source identified; production license unresolved**

Audit date: 2026-09-09

## Why this audit exists

Tennis Genome is intended to progress from research to a market-aware decision system. A dataset can be technically excellent and still be unsuitable for production because of license, provenance, timestamp, or redistribution restrictions.

The source layer therefore has a legal/provenance gate independent of model quality.

---

## Jeff Sackmann / Tennis Abstract datasets

The commonly used ATP/WTA historical repositories and mirrors state that the tennis databases/files/algorithms are licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)** and explicitly summarize the requirement as attribution plus non-commercial use.

Primary references to verify before any use:

- https://github.com/JeffSackmann/tennis_atp
- https://github.com/JeffSackmann/tennis_wta
- upstream README/license text or an archival mirror preserving that text

### Development decision

The repository may support a **Sackmann-style CSV adapter for research compatibility**, but it must not:

- bundle Sackmann data,
- silently download it,
- represent that dataset as cleared for a profit-oriented production system,
- assume that a third-party mirror grants broader rights than the upstream license.

If the project wants to rely on this data beyond clearly permitted non-commercial research, obtain appropriate permission/license or replace the production source.

This is a project governance rule, not legal advice.

---

## Research vs production source separation

### Research source may be accepted when

- provenance is known,
- license permits the intended research use,
- source hashes are recorded,
- fields and missingness are documented,
- timestamps are sufficiently understood for the experiment,
- limitations are disclosed in the report.

### Production source must additionally provide

- rights compatible with the intended use,
- reliable ongoing access/update cadence,
- documented historical coverage,
- stable player/match identifiers or a resolvable mapping,
- usable pre-match timestamps,
- clear terms for derived data/model use,
- acceptable cost and operational reliability.

---

## Timestamp audit requirements

Before ranking or other source fields can be called T0-safe, verify:

1. what the field represents,
2. when it was published or became available,
3. whether the historical file reconstructs that value retrospectively,
4. whether exact match start time is available,
5. whether same-day matches can be ordered reliably.

Until exact same-day timing is verified, Tennis Genome uses the conservative policy that all matches on a calendar date see ratings frozen before that date.

---

## Required source manifest fields

Every ingested raw source should eventually have:

- `source_id`,
- `provider`,
- `source_format`,
- `retrieved_at`,
- `source_version` or commit/snapshot identifier,
- `source_sha256`,
- `license_name`,
- `license_url`,
- `allowed_use_status`,
- `coverage_start`,
- `coverage_end`,
- `timestamp_semantics_status`,
- `notes`.

`allowed_use_status` should support at least:

- `research_allowed`,
- `production_allowed`,
- `permission_required`,
- `unknown_do_not_use`.

---

## Next source work

1. Verify exact ATP/WTA match/ranking field semantics for the chosen research snapshot.
2. Identify production-compatible providers for match history, rankings, and detailed statistics.
3. Compare provider coverage, identifiers, timestamps, rate limits, cost, and derived-use terms.
4. Keep source adapters behind a common canonical interface so changing providers does not change model definitions.
5. Never allow a license/provider change to silently alter the historical experiment population.

---

## Current conclusion

A Sackmann-style source is suitable as a **research-format target**, subject to its license and attribution requirements, but Tennis Genome currently has **no production-cleared canonical data provider**. Production data licensing remains an explicit blocker to deployment, not to early non-commercial methodological research where permitted.

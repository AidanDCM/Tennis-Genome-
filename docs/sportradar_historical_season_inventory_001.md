# Sportradar historical season inventory 001

Status: **pre-result inventory and panel-composition rule frozen before real historical chronology results are opened**

This layer closes a selection-bias gap left intentionally separate from the season-level chronology gate.

`SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001` can decide whether one provider season has complete exact-start chronology. By itself, however, that does not prove that the researcher attempted every season that was available. A clean recent panel could otherwise be manufactured by running the audit only on attractive seasons and never recording the failures.

This inventory makes the provider catalog itself the denominator.

## 1. Frozen tour scope

The source inventory uses exactly the project’s already-established main-tour Sportradar categories:

- ATP: `sr:category:3`, category name `ATP`;
- WTA: `sr:category:6`, category name `WTA`.

The separate WTA 125K/lower-tier category remains outside this population by the project’s prior population-preservation rule. Doubles, mixed and mixed-doubles competitions returned inside the ATP/WTA category catalogs remain visible in the competition inventory but are structural non-singles exclusions.

For this v2 source inventory, **competition `level` is retained metadata, not a selection rule**. The inventory must not later be narrowed to the provider levels that happen to have better chronology coverage.

## 2. Retained provider catalog evidence

Before chronology outcomes are interpreted, retain exact raw bytes for:

1. `Competitions by Category` for ATP category 3;
2. `Competitions by Category` for WTA category 6;
3. one `Competition Seasons` response for every `type=singles` competition returned by those two category catalogs.

The Competition Seasons evidence set must match the singles competition-ID set exactly. A missing response, an extra response, a season whose `competition_id` points elsewhere, duplicate competition IDs, or duplicate season IDs fails closed.

Sportradar currently documents Competition Seasons as a rolling window of at most three editions per competition, including current/newly created seasons. The inventory therefore describes the provider history that is actually accessible at the frozen snapshot, not unlimited historical tennis coverage.

## 3. Structural season status

Every returned season is retained. Its pre-chronology status is derived only from provider catalog metadata and the frozen UTC inventory snapshot date:

- `DISABLED_PROVIDER_SEASON`: provider `disabled=true`;
- `HISTORICAL_CANDIDATE`: not disabled and `end_date` is strictly before the inventory snapshot date;
- `NOT_YET_HISTORICAL`: not disabled and `end_date` is on or after the inventory snapshot date.

Using strict `< snapshot_date` keeps the snapshot day itself out of the completed-history set. No timeline completeness, model metric, prediction result or market result may influence this classification.

## 4. Historical-candidate disposition rule

Every `HISTORICAL_CANDIDATE` must receive exactly one final chronology disposition before an exact-time panel can be finalized:

- `CHRONOLOGY_ADMITTED`: the season’s retained audit independently passes `SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001`;
- `CHRONOLOGY_FAILED`: the season has a structurally valid audit, but the frozen chronology gate returns one or more deterministic failure reasons;
- `ACCESS_FAILURE`: the inventory-proven Season Summaries endpoint itself is unavailable under a retained finalizable provider response.

A historical candidate cannot be absent from this disposition set, and it cannot receive more than one disposition.

`NOT_YET_HISTORICAL` and `DISABLED_PROVIDER_SEASON` are carried into the final manifest automatically and cannot be supplied chronology evidence as though they were historical candidates.

## 5. Negative evidence versus broken evidence

A `CHRONOLOGY_FAILED` label is not an operator assertion.

The audit must first pass independent structural/integrity verification: identities, denominator counts, tour counts, event IDs, disposition arithmetic, chronology hashes, status semantics and timestamp validity must reproduce. Only after that can frozen gate failures such as missing timelines, missing starts, conflicting starts, invalid start times or an incomplete season become authoritative chronology-negative evidence.

A malformed or tampered audit blocks panel finalization. It is not converted into a convenient failure row.

## 6. Access failures are narrow

`ACCESS_FAILURE` is deliberately not a generic escape hatch.

The canonical evidence builder only finalizes an access failure when the exact inventory season’s Season Summaries endpoint returns retained HTTP evidence with one of:

- `401` or `403` -> `ACCESS_DENIED`;
- `404` or `410` -> `HISTORY_NOT_AVAILABLE`.

Transient `429` and `5xx` responses do not finalize a season and must be retried. If Season Summaries are available but one or more Sport Event Timelines are missing, that is chronology evidence handled by the chronology audit, not a season-level access failure.

The access artifact binds exact response-header and response-body SHA-256 identities.

## 7. Final exact-time panel manifest

`SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001` binds:

- raw inventory-file SHA-256;
- inventory semantic SHA-256;
- frozen chronology-admission policy SHA-256;
- every season and its final disposition;
- every chronology audit or access-failure evidence identity;
- deterministic failure reasons for chronology-negative seasons;
- exact selected season IDs;
- every admitted chronology-receipt semantic SHA-256;
- code SHA-256 identities for inventory, admission and panel finalization.

Only `CHRONOLOGY_ADMITTED` seasons receive `selected_for_exact_time_panel=true`.

The failed/access/active/disabled rows remain in the same panel manifest and may not be deleted merely because they are not model rows.

## 8. This still does not authorize a protected model comparison

The panel manifest closes season-selection leakage only. Before any protected v2 comparison uses the selected exact-time seasons, separate pre-result work must still establish:

- event/player crosswalk quality and failure rules;
- target-feature T0 availability;
- licensing/retention permissions;
- canonical event population construction across admitted seasons;
- dataset/code/runtime fingerprints;
- registered development/protected evaluation procedure.

The long-history Sackmann panel remains separate and conservatively prior-date. No timestamp semantics may be silently mixed.

This inventory/panel layer changes no TGE-Independent-v1 coefficient, prospective denominator, prospective metric, betting rule, or prospective sample count.

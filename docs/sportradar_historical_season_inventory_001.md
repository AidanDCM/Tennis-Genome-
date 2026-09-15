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

Every retained category or Competition Seasons response must also contain a valid timezone-aware provider `generated_at`. The ATP catalog, WTA catalog, and every required Competition Seasons response must all resolve to the same UTC calendar date. If the capture crosses UTC midnight, the inventory is invalid and must be recaptured as a single-date snapshot.

The canonical inventory `snapshot_at` is **not chosen by the operator**. It is the latest normalized provider `generated_at` among the complete retained catalog set. An operator-supplied capture time is only a sanity assertion and must resolve to that same provider UTC date; it cannot move the historical-season cutoff. The provider timestamps are retained in the inventory and revalidated when the artifact is reloaded.

Sportradar currently documents Competition Seasons as a rolling window of at most three editions per competition, including current/newly created seasons. The inventory therefore describes the provider history that is actually accessible at the frozen snapshot, not unlimited historical tennis coverage.

## 3. Structural season status

Every returned season is retained. Its pre-chronology status is derived only from provider catalog metadata and the provider-bound UTC inventory snapshot date:

- `DISABLED_PROVIDER_SEASON`: provider `disabled=true`;
- `HISTORICAL_CANDIDATE`: not disabled and `end_date` is strictly before the inventory snapshot date;
- `NOT_YET_HISTORICAL`: not disabled and `end_date` is on or after the inventory snapshot date.

Using strict `< snapshot_date` keeps the snapshot day itself out of the completed-history set. No operator-selected cutoff, timeline completeness, model metric, prediction result or market result may influence this classification.

## 4. Historical-candidate disposition rule

Every `HISTORICAL_CANDIDATE` must receive exactly one final chronology disposition before an exact-time panel can be finalized:

- `CHRONOLOGY_ADMITTED`: the season’s retained audit independently passes `SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001`;
- `CHRONOLOGY_FAILED`: the season has a structurally valid audit, but the frozen chronology gate returns one or more deterministic failure reasons;
- `ACCESS_FAILURE`: the inventory-proven Season Summaries resource itself is unavailable under a retained finalizable resource-level provider response.

A historical candidate cannot be absent from this disposition set, and it cannot receive more than one disposition.

`NOT_YET_HISTORICAL` and `DISABLED_PROVIDER_SEASON` are carried into the final manifest automatically and cannot be supplied chronology evidence as though they were historical candidates.

## 5. Negative evidence versus broken evidence

A `CHRONOLOGY_FAILED` label is not an operator assertion.

The audit must first pass independent structural/integrity verification: identities, denominator counts, tour counts, event IDs, disposition arithmetic, chronology hashes, status semantics and timestamp validity must reproduce. Only after that can frozen gate failures such as missing timelines, missing starts, conflicting starts, invalid start times or an incomplete season become authoritative chronology-negative evidence.

A malformed or tampered audit blocks panel finalization. It is not converted into a convenient failure row.

## 6. Access failures are narrow, self-contained and resource-level

`ACCESS_FAILURE` is deliberately not a generic escape hatch.

The authoritative real-data path only finalizes `HISTORY_NOT_AVAILABLE` from retained HTTP `404` or `410` evidence for the exact frozen inventory season’s Season Summaries endpoint after the existing endpoint/season identity checks pass.

`401` and `403` are **not** final historical-season evidence. Sportradar’s current Tennis v3 documentation states that a missing or invalid API key can itself return `403 Authentication Error`, while its response-code documentation describes `401` as lacking valid authentication credentials and `403` as lacking proper authorization. Those statuses therefore describe authentication/authorization state rather than proving that one required historical season is unavailable.

Accordingly:

- `401` / `403` -> non-finalizing authentication/authorization failure; correct access and retry;
- `404` / `410` -> eligible `HISTORY_NOT_AVAILABLE` resource evidence after exact frozen-season binding checks;
- `429` / `5xx` -> non-finalizing transient failure; retry.

Primary provider references:

- https://developer.sportradar.com/tennis/docs/tennis-ig-api-basics
- https://developer.sportradar.com/getting-started/docs/response-codes

If Season Summaries are available but one or more Sport Event Timelines are missing, that is chronology evidence handled by the chronology audit, not a season-level access failure.

An access-failure artifact is self-contained: it carries the exact retained response-header and response-body bytes in canonical base64 plus their SHA-256 identities. Loading the lower-level artifact must independently decode those bytes, reproduce both hashes, re-read the final HTTP status line from the retained headers, and re-derive its diagnostic failure class. A JSON object that merely declares plausible hashes or a convenient status is invalid. The endpoint path, provider-attempt timestamp, season, competition and tour remain bound to the frozen inventory row.

The lower-level object may still deserialize legacy 401/403 diagnostic evidence, but `SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-EVIDENCE-RECEIPT-001` rejects it before genuine panel construction and rejects any reloaded receipt whose access disposition is `ACCESS_DENIED`. This evidence-bound receipt is the authoritative real-data finalization path.

## 7. Final exact-time panel evidence receipt

The lower-level `SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001` manifest binds:

- raw inventory-file SHA-256;
- inventory semantic SHA-256;
- provider-derived inventory snapshot semantics;
- frozen chronology-admission policy SHA-256;
- every season and its final disposition;
- every chronology audit or self-contained access-failure evidence identity;
- deterministic failure reasons for chronology-negative seasons;
- exact selected season IDs;
- every admitted chronology-receipt semantic SHA-256;
- code SHA-256 identities for inventory, admission and panel finalization.

Only `CHRONOLOGY_ADMITTED` seasons receive `selected_for_exact_time_panel=true`.

The failed/access/active/disabled rows remain in the same panel manifest and may not be deleted merely because they are not model rows.

For genuine provider evidence, the lower-level manifest is then wrapped by `SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-EVIDENCE-RECEIPT-001`, which re-derives the frozen inventory from the retained raw provider catalogs, binds the exact raw-evidence identities and finalizer code, and enforces the resource-level access-failure rule above.

## 8. This still does not authorize a protected model comparison

The panel evidence closes season-selection and access-disposition leakage only. Before any protected v2 comparison uses the selected exact-time seasons, separate pre-result work must still establish:

- event/player crosswalk quality and failure rules;
- target-feature T0 availability;
- licensing/retention permissions;
- canonical event population construction across admitted seasons;
- dataset/code/runtime fingerprints;
- registered development/protected evaluation procedure.

The long-history Sackmann panel remains separate and conservatively prior-date. No timestamp semantics may be silently mixed.

This inventory/panel layer changes no TGE-Independent-v1 coefficient, prospective denominator, prospective metric, betting rule, or prospective sample count.

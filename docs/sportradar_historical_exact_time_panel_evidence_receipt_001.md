# Sportradar historical exact-time panel evidence receipt 001

Status: **pre-result finalization rule frozen before real historical chronology results are opened**

This receipt closes denominator, access-disposition and panel-reload integrity gaps left after `SPORTRADAR-HISTORICAL-SEASON-INVENTORY-001` and `SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001`.

The season inventory already records provider-payload hashes and the exact ATP/WTA competition and season rows. The panel finalizer already verifies that the serialized inventory is internally consistent. Internal consistency alone, however, does not prove that the serialized inventory still equals the retained provider evidence from which it was originally built. A coherently rewritten inventory could otherwise omit a competition or season while updating its internal counts and declared hashes consistently.

Likewise, a semantic hash only proves the bytes of one serialized panel object have not changed relative to that hash. If an attacker can rewrite the panel object and recompute the hash, the receipt still needs an independent structural verifier that reproduces the panel's allowed season rows, counts and selections from the embedded frozen inventory.

`SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-EVIDENCE-RECEIPT-001` therefore makes raw-evidence re-derivation, resource-level access-failure validation and panel-manifest re-verification mandatory for the real historical operator path.

## Required retained evidence

Panel finalization must receive the same exact retained raw files used to freeze the season inventory:

- ATP `Competitions by Category` for `sr:category:3`;
- WTA `Competitions by Category` for `sr:category:6`;
- one `Competition Seasons` response for every inventory-required singles competition.

The Competition Seasons binding set must still equal the singles competition set exactly. Missing or extra bindings fail closed.

## Mandatory re-derivation

Before chronology dispositions are converted into a final evidence receipt, the finalizer:

1. parses and independently verifies the supplied frozen inventory;
2. re-runs `build_sportradar_season_inventory` against the retained ATP/WTA category catalogs and complete Competition Seasons evidence set;
3. uses the inventory's provider-derived `snapshot_at` only as the same-UTC-date assertion required by the frozen inventory builder;
4. requires the rebuilt canonical inventory payload to equal the supplied frozen inventory payload exactly;
5. re-hashes every raw inventory file after re-derivation and requires those hashes to equal the hashes embedded in the frozen inventory;
6. validates that every proposed season-level access failure is a resource-level `404` or `410`, never an authentication/authorization failure;
7. builds the exact-time panel manifest from the complete frozen historical-candidate disposition set;
8. embeds both the frozen inventory and the panel manifest in the final evidence receipt.

An internally valid inventory that drops a competition or season is therefore rejected if it no longer re-derives from the retained provider bytes. Raw evidence that changes after the inventory freeze is also rejected.

## Authentication failures do not resolve a historical candidate

The authoritative evidence-bound finalizer does **not** accept `401` or `403` as a final historical-season disposition.

Sportradar's current Tennis v3 API documentation explicitly states that a missing or invalid API key can return HTTP `403 Authentication Error`. Its general response-code documentation describes `401` as lacking valid authentication credentials and `403` as lacking proper authorization. Those statuses therefore describe request/account execution state, not proof that one frozen historical season is unavailable.

Primary provider references:

- https://developer.sportradar.com/tennis/docs/tennis-ig-api-basics
- https://developer.sportradar.com/getting-started/docs/response-codes

For the real evidence path:

- `401` / `403` -> **non-finalizing authentication/authorization failure**; fix credentials/access and retry;
- `404` / `410` -> may finalize `HISTORY_NOT_AVAILABLE` only after the existing exact frozen-season endpoint/identity checks pass;
- `429` / `5xx` -> **non-finalizing transient failure**; retry.

The lower-level `ProviderAccessFailureEvidence` object may still deserialize 401/403 evidence for legacy diagnostics and isolated tests. That does not make it admissible. `build_evidence_bound_exact_time_panel_receipt` rejects it before panel construction, and `EvidenceBoundExactTimePanelReceipt` rejects any reloaded manifest carrying legacy `ACCESS_DENIED` as a final access disposition.

This distinction is necessary to prevent an invalid/missing key from becoming a convenient way to exclude an otherwise inventory-required season.

## Panel-manifest reload integrity

A final evidence receipt does not trust the embedded panel manifest merely because its semantic SHA-256 has been recomputed successfully.

Every time `EvidenceBoundExactTimePanelReceipt` is loaded, the panel manifest is independently checked against the embedded frozen inventory. The verifier requires:

- the panel season-ID set to equal the frozen inventory season-ID set exactly, with no duplicates or omissions;
- canonical panel row ordering;
- each row's tour, competition ID/name, season dates and inventory status to equal its frozen inventory row;
- `NOT_YET_HISTORICAL` and `DISABLED_PROVIDER_SEASON` rows to retain their structural disposition, remain unselected and carry no chronology evidence fields;
- every historical candidate to resolve only as `CHRONOLOGY_ADMITTED`, `CHRONOLOGY_FAILED`, or admissible resource-level `ACCESS_FAILURE`;
- admitted rows to be selected and carry the expected chronology/audit SHA-256 identities with no failure reasons;
- failed chronology rows to remain unselected, retain their chronology/audit SHA-256 identities and carry at least one failure reason;
- access-failure rows to remain unselected, carry only their access-evidence semantic identity, carry no chronology hashes, and have exactly `HISTORY_NOT_AVAILABLE` as the failure reason;
- all disposition counts to reproduce from the rows, with `historical_candidate_count` reproducing from the frozen inventory;
- `selected_season_ids` to reproduce exactly from the admitted rows;
- admitted receipt SHA-256 identities to be canonically ordered, unique, valid SHA-256 values, and equal in count to admitted seasons;
- the frozen chronology-admission policy semantic identity to match the current frozen policy.

This means a coherent rewrite of a panel row, its aggregate counts, its selected IDs and the panel semantic hash still fails if those claims no longer agree with the embedded frozen inventory and structural rules.

## Receipt bindings

The final receipt embeds both the complete frozen season inventory and the complete `SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001` manifest and binds:

- the panel-manifest semantic SHA-256;
- the inventory file SHA-256;
- the inventory semantic SHA-256;
- the ATP category-catalog raw SHA-256;
- the WTA category-catalog raw SHA-256;
- every `competition_id -> Competition Seasons` raw SHA-256;
- one deterministic aggregate SHA-256 over the canonically ordered raw-evidence identity set;
- the SHA-256 of the evidence-bound finalizer code itself.

The raw-evidence identities are canonically ordered and uniqueness checked. When the receipt is loaded again, it revalidates the embedded frozen inventory, panel structure/counts/selections, nested panel/inventory identities, exact raw-evidence identity map, aggregate evidence-set identity, frozen admission policy and resource-level access-failure rule.

## Authoritative operator command

For genuine historical Sportradar execution, use the evidence-bound finalizer rather than the lower-level bare panel-manifest CLI:

```bash
python -m tennis_genome.research_workbench.sportradar_exact_time_panel_evidence \
  --inventory <season-inventory.json> \
  --atp-competitions <atp-competitions.json> \
  --wta-competitions <wta-competitions.json> \
  --seasons <COMPETITION_ID>::<competition-seasons.json> \
  --repo-root . \
  --admitted-audit <SEASON_ID>::<admitted-audit.json> \
  --failed-audit <SEASON_ID>::<failed-audit.json> \
  --access-failure <404-or-410-access-failure-evidence.json> \
  --output <exact-time-panel-evidence-receipt.json>
```

Repeat `--seasons` for every required singles competition and repeat disposition evidence options as required by the frozen inventory.

The lower-level `sportradar_exact_time_panel` module remains useful for isolated deterministic unit testing of disposition logic, but a bare manifest from that path is **not** sufficient real-data evidence after this rule.

## Scientific boundary

This receipt proves only that the exact-time panel denominator and dispositions are bound to the retained local provider evidence and frozen code identities under the preregistered finalization rules. It does not prove provider authenticity beyond the retained bytes, licensing permission, event/player crosswalk quality, target-feature T0 availability, modeling-dataset validity, predictive superiority, sportsbook edge, or profitability.

No TGE-Independent-v1 coefficient, prospective cohort, metric, market rule, prospective N, or protected-model result changes here.
